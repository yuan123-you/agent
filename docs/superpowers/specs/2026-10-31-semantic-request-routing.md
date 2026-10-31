# Semantic request routing and dialogue decisions

## User requirement
Stop repairing post-purchase understanding by adding words. Use semantic understanding to decide whether to clarify, retrieve evidence or proceed with existing tools. Preserve existing evidence and authorization protections.

## Design
- Existing embeddings classify first-turn business requests against labelled intent/action examples using normalized cosine similarity and a top-decision margin. Examples are not substring patterns. Low-confidence, ambiguous and contextual requests abstain to a separately configured intent model.
- A validated request decision contains intent, next_step (assist/retrieve/clarify), and a controlled missing-information slot. Clarification wording is program-owned and contains no unverified policy claims.
- Intent-model fallback consumes recent dialogue and emits the same decision. Failure produces a neutral clarification, not a keyword-derived shopping/policy guess.
- Natural-language business keywords no longer select fast intent or post-purchase clarification. Preserve deterministic identity/time/naming shortcuts, explicit authorization guards, literal data extraction and evidence-output defense-in-depth.
- Per-turn decisions reset in checkpoint assembly. Multi-turn replies use the contextual model rather than reapplying a first-turn example to a short isolated utterance.
- Keep the existing answer-generation model, embedding model/space, knowledge collections, source approval, rendered SSE terminal answer, order confirmation cards and ownership checks.

## Acceptance
- Unseen paraphrases and customer-versus-assistant complaints; explicit return/quality/policy requests; ambiguous requests; negative/conditional human requests.
- Context continuation and switching, no clarification loop when the goal is already stated, no reuse of stale per-turn decisions.
- Bad vectors, incompatible dimensions, zero/nonfinite vectors, low score/margin, cache concurrency, provider timeout/malformed model JSON all fail safely.
- True streaming must publish rendered terminal text, not classifier/planner JSON; clarifications never call kb_search or action tools.
- Real embedding/model evaluation uses held-out questions not present in the route examples. Do not lower safety thresholds merely to make a sample pass.

## Non-goals
No answer-generation/embedding model change, paid-service migration, new Milvus collection, unrelated UI/commerce changes, arbitrary policy promises or automatic mutation of orders/refunds.

## Approved intent-model evaluation (2026-10-31)
The user explicitly approved provisioning/evaluating a stronger local intent model after the existing 1.5B model failed real multi-turn acceptance. Evaluate in an isolated, resource-bounded Ollama service; do not evict production generation weights. Add optional intent-specific endpoint settings with backwards-compatible shared-provider defaults. Production cutover requires real semantic, latency, resource and HTTP-stream acceptance; downloading a candidate is not approval to bypass that gate.
