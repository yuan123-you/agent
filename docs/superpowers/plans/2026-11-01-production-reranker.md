# Production cross-encoder reranking plan

Goal: enable real cross-encoder scoring after dense/BM25 RRF fusion, preserving the verified production models.
Baseline: production commit 323b1ac9ad4f25ed92957f8dfc2f0270d6698d26. Work only on codex/enable-production-reranker; do not ship the blocked generation upgrade.

Architecture: existing typed HTTP client calls an internal CPU ONNX BAAI/bge-reranker-v2-m3 service. Pin one INT8 export and tokenizer by revision and SHA256. Recall dense20/BM2520, fuse10, rerank10, approve4. Preserve thresholds, source metadata, full approved evidence, collections and confirmation checks.

- [ ] Write failing service and production configuration tests.
- [ ] Implement bounded cross-encoder service, verified downloader and resource-limited internal service. No generation-based JSON scoring.
- [ ] Run focused/full AI and auxiliary tests; keep unrelated frontend baseline failure separate.
- [ ] Build isolated CPU service, test real published policy pairs and actual hybrid pipeline. Check ranking, negative queries and timings without lowering thresholds.
- [ ] Review and push branch. Under deployment lock, snapshot old image/config and original container IDs. Start reranker and recreate only AI config using its existing image.
- [ ] Verify real scores, fallback, original models, readiness/public API and read-only QA stream; rollback on failure.

Non-goals: product reranking, generation upgrades, data/index rebuilds, paid services or unrelated UI changes. Relevance ranking is not answer entailment.
