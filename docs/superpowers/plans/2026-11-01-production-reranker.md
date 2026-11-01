# Production cross-encoder reranking plan

Goal: enable real cross-encoder scoring after dense/BM25 RRF fusion, preserving the verified production models.
Baseline: production commit 323b1ac9ad4f25ed92957f8dfc2f0270d6698d26. Work only on codex/enable-production-reranker; do not ship the blocked generation upgrade.

Architecture: existing typed HTTP client calls an internal CPU ONNX BAAI/bge-reranker-v2-m3 service. Pin one INT8 export and tokenizer by revision and SHA256. Recall dense20/BM2520, fuse10, rerank10, approve4. Preserve thresholds, source metadata, full approved evidence, collections and confirmation checks.

- [x] Write failing service and production configuration tests.
- [x] Implement bounded cross-encoder service, verified downloader and resource-limited internal service. No generation-based JSON scoring.
- [x] Run focused/full AI and auxiliary tests; keep unrelated frontend baseline failure separate.
- [x] Build isolated CPU service, test real published policy pairs and actual hybrid pipeline. Check ranking, negative queries and timings without lowering thresholds.
- [x] Review and push branch. Under deployment lock, snapshot old image/config and original container IDs. Start reranker and deploy the reviewed RAG-only AI image, retaining the existing model weights.
- [x] Verify real scores, fallback, original models, readiness/public API and read-only QA stream; rollback on failure.

Non-goals: product reranking, generation upgrades, data/index rebuilds, paid services or unrelated UI changes. Relevance ranking is not answer entailment.


Integration follow-up: first HTTP rollout was rejected and rolled back when the unchanged
1.5B generator inverted the approval rule despite correct high-scoring sources. A controlled
same-model/same-evidence test justified only moving the original question after complete
evidence. Trace evidence also justified limiting native background embedding batches to2
and keeping the same encoder resident24h. These three small app-file changes are included
in the second candidate; no semantic-router/generation-model upgrade is included. Deadline
formatting failure remains safely refused and must not be counted as a successful answer.

Final result: deployed2dbf495,32 production gates passed;10 healthy services, QA disabled, owned evaluators removed. First failed attempt and remaining conservative/formatting limits are retained in the QA report.
