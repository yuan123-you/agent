"""Internal CPU cross-encoder: actual pair logits, never generated JSON scores."""
import asyncio
from contextlib import asynccontextmanager, suppress
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Annotated, Literal

import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

MODEL_ID = "BAAI/bge-reranker-v2-m3"
MODEL_DIR = Path(os.environ.get("MODEL_DIR", "/models"))
LOCK = json.loads(Path(__file__).with_name("model-lock.json").read_text())
logger = logging.getLogger("reranker")


def normalized_scores(logits, count):
    values = np.asarray(logits)
    if values.shape not in ((count,), (count, 1)) or not np.isfinite(values).all():
        raise ValueError("invalid cross-encoder logits")
    values = values.reshape(-1).astype(np.float64)
    return (1 / (1 + np.exp(-np.clip(values, -60, 60)))).tolist()


class CrossEncoder:
    def __init__(self, session, tokenizer, *, batch_size=2):
        self.session, self.tokenizer = session, tokenizer
        self.batch_size = batch_size
        self.inputs = {item.name for item in session.get_inputs()}

    def scores(self, query, documents):
        scores = []
        for start in range(0, len(documents), self.batch_size):
            batch = documents[start:start + self.batch_size]
            encoded = self.tokenizer.encode_batch([(query, doc) for doc in batch])
            arrays = {"input_ids": [e.ids for e in encoded],
                      "attention_mask": [e.attention_mask for e in encoded],
                      "token_type_ids": [e.type_ids for e in encoded]}
            inputs = {key: np.asarray(value, dtype=np.int64)
                      for key, value in arrays.items() if key in self.inputs}
            logits = self.session.run(None, inputs)[0]
            scores.extend(normalized_scores(logits, len(batch)))
        return scores


def load_engine():
    # Verify before importing/loading native runtime. Offline startup cannot silently
    # replace the pinned model or download extra weights on a user's request.
    for filename, record in LOCK["files"].items():
        with (MODEL_DIR / filename).open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != record["sha256"]:
            raise ValueError("model artifact checksum mismatch")
    import onnxruntime as ort
    from tokenizers import Tokenizer
    options = ort.SessionOptions()
    options.intra_op_num_threads = int(os.environ.get("RERANK_THREADS", "2"))
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    tokenizer = Tokenizer.from_file(str(MODEL_DIR / "tokenizer.json"))
    tokenizer.enable_truncation(max_length=1024, strategy="longest_first")
    tokenizer.enable_padding(pad_id=1, pad_token="<pad>")
    session = ort.InferenceSession(str(MODEL_DIR / "model.onnx"), sess_options=options,
                                   providers=["CPUExecutionProvider"])
    engine = CrossEncoder(session, tokenizer, batch_size=2)
    engine.scores("模型预热", ["规则检索相关性预热"])
    return engine


@asynccontextmanager
async def lifespan(app):
    app.state.engine = await run_in_threadpool(load_engine)
    app.state.inference_lock = asyncio.Lock()
    app.state.inference_task = None
    try:
        yield
    finally:
        pending = app.state.inference_task
        if pending is not None:
            with suppress(Exception):
                await asyncio.shield(pending)


app = FastAPI(lifespan=lifespan)
Document = Annotated[str, Field(min_length=1, max_length=12000)]


class RerankRequest(BaseModel):
    model: Literal["BAAI/bge-reranker-v2-m3"] = MODEL_ID
    query: Annotated[str, Field(min_length=1, max_length=2000)]
    documents: Annotated[list[Document], Field(min_length=1, max_length=20)]
    top_n: Annotated[int, Field(ge=1, le=20)] = 20


@app.get("/health")
async def health():
    return {"status": "UP", "model": MODEL_ID, "revision": LOCK["revision"],
            "precision": "int8", "provider": "CPUExecutionProvider"}


@app.post("/v1/rerank")
async def rerank(request: RerankRequest):
    lock, engine = app.state.inference_lock, app.state.engine
    # No waiting queue: check plus uncontended acquire has no suspension point.
    if lock.locked():
        raise HTTPException(503, "reranker busy", headers={"Retry-After": "1"})
    await lock.acquire()

    async def infer():
        try:
            return await run_in_threadpool(engine.scores, request.query, request.documents)
        finally:
            lock.release()

    # The worker-owning task keeps the permit even when its caller is cancelled.
    task = asyncio.create_task(infer(), name="reranker-inference")
    app.state.inference_task = task
    def completed(done):
        if app.state.inference_task is done:
            app.state.inference_task = None
        if not done.cancelled():
            done.exception()  # Observe failures even if the HTTP caller disconnected.
    task.add_done_callback(completed)
    try:
        scores = await asyncio.shield(task)
        if len(scores) != len(request.documents) or not all(np.isfinite(scores)):
            raise ValueError("invalid score count")
        indices = sorted(range(len(scores)), key=lambda i: -scores[i])[:request.top_n]
        return {"model": MODEL_ID, "results": [
            {"index": i, "relevance_score": scores[i]} for i in indices]}
    except Exception as exc:
        logger.warning("cross-encoder unavailable (%s)", type(exc).__name__)
        raise HTTPException(503, "reranker unavailable") from None
