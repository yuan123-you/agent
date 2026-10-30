# Arrival-expression clarification hotfix — 2026-10-30

- Deployed application commit: `7c24714f3a4bc265761ae975fd374bcb3dcdff33`, pushed on `dev`.
- Screenshot reproduction: `到货后不满意怎么办` incorrectly missed the deterministic clarification route and could fall through to an irrelevant knowledge lookup / insufficient-evidence response.
- Root cause: the existing post-purchase predicate recognized 商品/买/收到/收货 but omitted 到货/货到/到手/签收. The production change adds only those four delivery signals, preserving the exclusions for explicit return, quality, policy and human-service requests.
- Red before the change: four direct intent/clarification cases and the full LangGraph/SSE screenshot case failed. Green after: **579 AI tests + 32 evaluation/hygiene tests passed**.

## Actual production HTTP verification

All five requests went through the frontend proxy/backend/AI HTTP dialogue path. Each returned exactly:

> 您是想退换货，还是商品存在质量问题？

Each stream completed with token/done, zero unrelated citations, and **no tool_call or tool_result events**. In particular, the original screenshot wording no longer triggers a zero-hit knowledge search.

| Input | Observed seconds | Citation count |
|---|---:|---:|
| 到货后不满意怎么办 | 0.12 | 0 |
| 货到了不满意怎么办 | 0.1 | 0 |
| 签收后不满意怎么办 | 0.09 | 0 |
| 拿到手不满意怎么办 | 0.09 | 0 |
| 商品购买后不满意怎么办 | 0.09 | 0 |

**52 production checks passed**; all nine services were healthy afterward. Running-source hashes matched all ten changed AI production Python files inherited from the knowledge-answer release. Only the AI service container was replaced; the other eight container IDs were unchanged. The synthetic QA account was restored to DISABLED and its test conversations were closed.

## Scope and preservation

- This is a targeted synonym-routing repair, not a claim of complete natural-language intent coverage.
- The prior knowledge synthesis, source validation, contradiction guard and rendered-SSE-finalization fixes remain in place.
- No model/provider, frontend/backend container, schema, order, payment or volume migration was performed.
- The previous AI image is retained as `aimall-rollback-ai-service:kb-7c24714`, with private configuration/container records and a permission-restricted database backup.
- Existing stored messages were preserved; the screenshot's historical reply is not rewritten. New replies use the corrected route.
- Latencies above are individual observations, not a performance SLA.
