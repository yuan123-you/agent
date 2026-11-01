# CPU knowledge reranker

A genuine cross-encoder, not an Ollama prompt requesting a numeric score. The service
loads the pinned INT8 ONNX export of BAAI/bge-reranker-v2-m3; it encodes each query/document
pair and applies sigmoid to the classification logit. Scores are relative relevance
signals, not proof of factual entailment or calibrated probabilities.

## Production path

Dense20 + BM2520 run in parallel, metadata filtering precedes RRF10, HTTP reranking
scores all10, and the existing pipeline selects4 complete approved chunks. The legacy
Ollama/product reranker remains disabled. Existing answerability thresholds, source
approval and citation/dump guards remain unchanged. No embedding reindex is needed.

The internal service exposes `/v1/rerank` and `/health`, without a published host port.
It uses3 CPU threads, a3 GiB memory limit, one inference at a time, immediate busy503,
and Uvicorn admission limits. A cancelled HTTP caller cannot release the still-running
worker's inference permit. The AI HTTP timeout is20s; transport/model failures use the
existing RRF fallback with `degraded_reasons=reranker_unavailable`, never invented scores.

## One-time bootstrap

Use the normal private production env file; never place credentials in this directory.

```sh
C="docker compose --env-file /srv/aimall/secrets/production.env -f deploy/compose.production.yml"
$C build ai-service reranker
docker volume create --label com.docker.compose.project=aimall-prod --label com.docker.compose.volume=reranker-data aimall-prod_reranker-data
docker run --rm --memory 256m --cpus 1 -v aimall-prod_reranker-data:/models aimall-prod-reranker python download_model.py /models
$C up -d --no-deps --wait reranker
$C up -d --no-build --no-deps --wait ai-service
```

The downloader verifies SHA256 before publishing each file, reuses only verified
files and removes corrupt partial downloads. Runtime mounts weights read-only and
performs checksum verification before native model loading. No runtime model downloads,
PyTorch installation, paid service or arbitrary remote Python code are used.
Build the AI image from this production-base branch, which changes only evidence
message order and native embedding batch configuration. Chat/intent weights remain
qwen2.5:1.5b and embeddings remain dmeta/768. Do not build the unrelated blocked
generation-model/semantic-router branch during this rollout.

## Provenance

- Model: https://huggingface.co/BAAI/bge-reranker-v2-m3
- Pinned export: https://huggingface.co/onnx-community/bge-reranker-v2-m3-ONNX/tree/6f5ff65298512715a1e669753bc754d2bc8f367b
- Exact artifact digests: `model-lock.json` (model and tokenizer together about561 MiB).

The export is maintained by onnx-community, not the original BAAI publisher. The
lock pins the actual exported files, not an unverified assertion about its upstream
base-model commit. Original model license is Apache-2.0 per the publisher's card.

## Verification boundaries

Production uses a two-text native embedding batch cap and24h encoder keepalive to
avoid repeated cold loads and long waits behind bulk document encoding; this changes
neither the encoder nor its indexed vector space.

Unit tests cover pair ordering, sigmoid, stable output indices, request limits,
verified downloads, overload and cancellation. They do not measure model accuracy.
The real ARM64 sample has7 supported-policy and2 absent-topic queries: relevant
chunks reached final4 for all7 policy queries; both negatives stayed unanswerable.
One positive repair-postage query remains below the unchanged confidence threshold,
so the combined answerability check is8/9, not9/9. This conservative refusal is recorded,
not repaired with lower thresholds. Relevance reranking does not fix all weaknesses
of the unchanged1.5B answer generator.
