"""Contract tests; real model quality/latency is verified separately on ARM64."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient
from deploy.reranker import server


def test_cross_encoder_scores_pairs_with_global_sigmoid_and_original_order():
    seen = []
    class Tokenizer:
        def encode_batch(self, pairs):
            seen.extend(pairs)
            return [SimpleNamespace(ids=[int(doc)], attention_mask=[1], type_ids=[0])
                    for query, doc in pairs]
    class Session:
        def get_inputs(self):
            return [SimpleNamespace(name="input_ids"), SimpleNamespace(name="attention_mask")]
        def run(self, output, inputs):
            assert set(inputs) == {"input_ids", "attention_mask"}
            return [inputs["input_ids"].astype(float)]
    engine = server.CrossEncoder(Session(), Tokenizer(), batch_size=2)
    scores = engine.scores("费用", ["-2", "2", "0"])
    assert seen == [("费用", "-2"), ("费用", "2"), ("费用", "0")]
    assert scores == pytest.approx([.119202922, .880797078, .5])


def test_nonfinite_model_logits_fail_closed():
    with pytest.raises(ValueError):
        server.normalized_scores(np.array([[float("nan")]]), 1)
    with pytest.raises(ValueError):
        server.normalized_scores(np.array([[1., 2.]]), 1)


@pytest.fixture
def client(monkeypatch):
    fake = SimpleNamespace(scores=lambda query, docs: [.2, .9, .9][:len(docs)])
    monkeypatch.setattr(server, "load_engine", lambda: fake)
    with TestClient(server.app) as client:
        yield client


def test_api_sorts_scores_preserves_indices_and_breaks_ties_stably(client):
    response = client.post("/v1/rerank", json={"model": server.MODEL_ID,
        "query": "维修运费", "documents": ["无关", "证据一", "证据二"], "top_n": 2})
    assert response.status_code == 200
    assert response.json()["results"] == [
        {"index": 1, "relevance_score": .9}, {"index": 2, "relevance_score": .9}]
    health = client.get("/health").json()
    assert health["model"] == server.MODEL_ID and health["precision"] == "int8"


@pytest.mark.parametrize("change", [
    {"documents": []}, {"documents": ["x"]*21}, {"query": ""},
    {"documents": ["x"*12001]}, {"top_n": 0}, {"model": "unknown"},
])
def test_api_rejects_unbounded_or_wrong_model_requests(client, change):
    request = {"model": server.MODEL_ID, "query": "规则", "documents": ["资料"], "top_n": 1}
    request.update(change)
    assert client.post("/v1/rerank", json=request).status_code == 422


@pytest.mark.asyncio
async def test_busy_inference_is_bounded_and_returns_retryable_503(monkeypatch):
    import httpx
    monkeypatch.setattr(server, "load_engine", lambda: SimpleNamespace(scores=lambda q, d: [.5]))
    async with server.lifespan(server.app):
        await server.app.state.inference_lock.acquire()
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url="http://test") as client:
                async with asyncio.timeout(1):
                    response = await client.post("/v1/rerank", json={"query": "规则", "documents": ["正文"]})
            assert response.status_code == 503
        finally:
            server.app.state.inference_lock.release()


def test_missing_or_corrupt_weights_do_not_pass_startup(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "MODEL_DIR", tmp_path)
    with pytest.raises((FileNotFoundError, ValueError)):
        server.load_engine()


def test_production_enables_real_http_fine_ranking_without_changing_active_models():
    text = (Path(__file__).parent / "compose.production.yml").read_text(encoding="utf-8")
    assert "RAG_RERANKER_ENABLED: 'true'" in text
    assert "RAG_RERANKER_BASE_URL: http://reranker:8001" in text
    assert "RAG_RERANKER_MODEL: BAAI/bge-reranker-v2-m3" in text
    assert "RERANKER_ENABLED: 'false'" in text
    assert "LLM_CHAT_MODEL: qwen2.5:1.5b" in text
    assert "EMBEDDING_MODEL: shaw/dmeta-embedding-zh" in text
    section = text.split("  reranker:\n", 1)[1].split("  ai-service:\n", 1)[0]
    assert "ports:" not in section and "mem_limit: 3g" in section


def test_production_declares_the_read_only_model_volume():
    text = (Path(__file__).parent / "compose.production.yml").read_text(encoding="utf-8")
    assert "  reranker-data:" in text.split("\nvolumes:", 1)[1]


def test_downloader_checksums_and_reuses_only_verified_files(tmp_path, monkeypatch):
    import hashlib
    import io
    from deploy.reranker import download_model
    content = b"pinned model bytes"
    digest = hashlib.sha256(content).hexdigest()
    monkeypatch.setattr(download_model, "LOCK", {"repository": "test/repo", "revision": "fixed",
        "files": {"model.onnx": {"path": "model.onnx", "sha256": digest}}})
    monkeypatch.setattr(download_model.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(content))
    download_model.download(tmp_path)
    assert (tmp_path/"model.onnx").read_bytes() == content
    monkeypatch.setattr(download_model.urllib.request, "urlopen", lambda *a, **k: pytest.fail("must reuse verified file"))
    download_model.download(tmp_path)


def test_corrupt_download_is_not_published_or_left_as_a_partial_file(tmp_path, monkeypatch):
    import io
    from deploy.reranker import download_model
    monkeypatch.setattr(download_model, "LOCK", {"repository": "test/repo", "revision": "fixed",
        "files": {"model.onnx": {"path": "model.onnx", "sha256": "0"*64}}})
    monkeypatch.setattr(download_model.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(b"corrupt"))
    with pytest.raises(ValueError):
        download_model.download(tmp_path)
    assert not list(tmp_path.iterdir())


@pytest.mark.asyncio
async def test_busy_request_has_no_waiting_queue(monkeypatch):
    from fastapi import HTTPException
    monkeypatch.setattr(server, "load_engine", lambda: SimpleNamespace(scores=lambda q, d: [.5]))
    async with server.lifespan(server.app):
        await server.app.state.inference_lock.acquire()
        tasks = [asyncio.create_task(server.rerank(server.RerankRequest(query="规则", documents=["正文"]))) for _ in range(100)]
        try:
            await asyncio.sleep(0)
            assert all(task.done() for task in tasks)
            assert all(isinstance(task.exception(), HTTPException) and task.exception().status_code == 503 for task in tasks)
        finally:
            for task in tasks:
                if not task.done(): task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            server.app.state.inference_lock.release()


@pytest.mark.asyncio
async def test_cancelled_caller_does_not_release_worker_owned_inference_permit(monkeypatch):
    import threading
    from fastapi import HTTPException
    started, release, finished = threading.Event(), threading.Event(), threading.Event()
    def slow_score(query, docs):
        started.set()
        release.wait(2)
        finished.set()
        return [.5]
    monkeypatch.setattr(server, "load_engine", lambda: SimpleNamespace(scores=slow_score))
    async with server.lifespan(server.app):
        task = asyncio.create_task(server.rerank(server.RerankRequest(query="规则", documents=["正文"])))
        assert await asyncio.to_thread(started.wait, 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError): await task
        try:
            assert server.app.state.inference_lock.locked()
            with pytest.raises(HTTPException) as error:
                await server.rerank(server.RerankRequest(query="另一条规则", documents=["正文"]))
            assert error.value.status_code == 503
        finally:
            release.set()
            assert await asyncio.to_thread(finished.wait, 1)
            await asyncio.sleep(.02)
        assert not server.app.state.inference_lock.locked()


def test_production_recall_fusion_and_fine_ranking_windows_are_explicit():
    text = (Path(__file__).parent / "compose.production.yml").read_text(encoding="utf-8")
    for key, value in {"RAG_VECTOR_RECALL_K":20, "RAG_BM25_RECALL_K":20,
                       "RAG_RRF_TOP_K":10, "RAG_FINAL_TOP_K":4}.items():
        assert f"{key}: '{value}'" in text


def test_production_query_encoder_does_not_expire_between_slow_turns_or_run_huge_batches():
    text=(Path(__file__).parent/"compose.production.yml").read_text(encoding="utf-8")
    assert "OLLAMA_KEEP_ALIVE: 24h" in text
    assert "OLLAMA_EMBED_BATCH_SIZE: '2'" in text
