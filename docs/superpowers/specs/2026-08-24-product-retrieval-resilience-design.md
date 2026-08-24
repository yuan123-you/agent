# Product Retrieval Resilience and Agent Loop Design

**Date:** 2026-08-24

## Goal

Make product retrieval useful immediately after startup and during Milvus/Embedding failures, while preventing the Agent from repeatedly executing an identical tool call.

## Root causes

1. Product BM25 is owned by `ProductIndex`, whose constructor requires Milvus, and is rebuilt only after all product embeddings and vector writes finish. Startup evaluation therefore falls back to SQL for minutes.
2. `hybrid_product_search` treats vector failure as failure of the entire hybrid pipeline, discarding an otherwise ready BM25 corpus.
3. The graph only limits total tool loops; it does not recognize that the model proposed the same call after already receiving its result.

## Design

- Give the in-memory `ProductCorpus` its own process-wide getter independent of Milvus.
- Rebuild the corpus immediately after fetching products, before embedding work.
- Catch vector-leg failures inside hybrid retrieval and continue with BM25; return `None` only when no corpus exists.
- Before executing tools, compare the latest normalized tool-call signatures with previous AI tool calls. If every proposed call is already present, route to the existing no-tools finalizer instead of executing duplicates.
- Do not add query rewriting or change intent routing until a post-fix live evaluation justifies it.

## Metrics

Re-run the same safe four-case live smoke. Compare product Recall@5/MRR, P50/P95, Token usage, and observed tool executions against the phase-2 result.
