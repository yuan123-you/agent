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

## Approved answer-generation evaluation (2026-10-31)
After the candidate passed semantic routing but failed real policy synthesis and was rolled back, the user explicitly approved evaluating/upgrading the local answer-generation model as well. This supersedes the original generation-model preservation requirement only. Keep the embedding model/space, complete approved knowledge evidence, ownership/confirmation/citation/dump guards, and business data unchanged. Evaluate against the same failing evidence without citation repair or forced references. Candidate: the already-provisioned instruction-only `qwen3:4b-instruct`, first in the isolated resource-bounded instance. Selection and deadlines depend on actual answer correctness, citations, latency and resource observations; no paid provider migration.

## Information-sufficiency clarification boundary
A personal eligibility question without the required product category/state is not a complete policy-adjudication task. An unspecified after-sale postage question may also omit whether it means return/exchange or repair. Resolve those gaps semantically with controlled `ASK_PRODUCT` / `ASK_SHIPPING` cards before retrieval. Generic rule requests and requests whose relevant context has already been supplied still retrieve real evidence. An explicit handling request still performs read-only order lookup first; missing details do not negate the expressed handling goal.

A topic-only embedding match cannot certify that case information is complete, so confident policy-topic matches receive language-model completeness confirmation. A disagreement asks which policy scope is intended, not an unrelated shopping/chat guess. Store only the established read-only policy topic through these clarifications, never purchase/human authorization. Clarification-only turns report neither retrieval use nor citation requirement. A generated failure is not counted as a business clarification.

The original wording and all scope/authorization guards remain authoritative. A resolved retrieval topic is data for both search and synthesis so a short continuation does not become an unrelated encyclopedic answer.

Postage ambiguity may also be handled by retrieving and explaining explicitly conditional alternatives, then asking which applies. It must not silently apply a return-postage rule to a repair case or vice versa. Such a grounded conditional response is distinct from guessing the actual purpose; the live factual gate still applies.
