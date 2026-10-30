# Knowledge-answer production release — 2026-10-30

## Released application

- Branch: `dev`; application source commit: `84cf0c636623d401353bce88efbf94cd5f00b5cd`.
- Only the AI service image/container was replaced. The backend, frontend, MySQL, Redis, MinIO, Milvus, conversation-model and embedding-model container IDs were unchanged during this release.
- Existing model/provider retained: `qwen2.5:1.5b`; no new model download, schema migration, order/payment operation or volume deletion.
- All nine services healthy after verification. Public domain product API also passed.
- **38 production checks passed**, including running-image hashes for all ten changed production Python files, effective settings, HTTP SSE, preservation checks and synthetic-account cleanup.

## Actual HTTP dialogue verification

These requests went through the running frontend proxy/backend/AI HTTP chain, not a mocked model or a direct node call. Times below are end-to-end observations, not performance guarantees.

| Question | Observed behavior | Seconds |
|---|---|---:|
| 商品购买后不满意怎么办 | Asked one relevant question: 您是想退换货，还是商品存在质量问题？ No document dump or unsolicited complaint escalation. | 0.12 |
| 平台无理由退货规则是什么？ | Returned a concise conditional policy answer with an approved `[S1]` citation; no large document headings or copied chapters. | 35.95 |
| 商品拆封了还能无理由退货吗？ | The known small-model contradiction was rejected; requested the product name and usage details rather than issuing an unsupported blanket refusal. | 60.61 |

The dedicated synthetic QA account was restored to DISABLED, and its verification conversations were closed. No buyer account was used for testing.

## Fixes required by actual runtime evidence

1. Removed the original extractive document-dump branch; legacy mode values now enter the same evidence-grounded answering path.
2. Complete approved evidence only, bounded tool-free generation, safe handling of timeout/provider failure/truncation/malformed output, and shared rejection of long source dumps.
3. The actual SDK rewrites `max_tokens` to `max_completion_tokens`. The existing legacy server ignored the latter, so an opt-in `KB_LEGACY_MAX_TOKENS=true` now supplies its supported wire field through `extra_body`. Normal providers remain unchanged.
4. The small model returns structured points/source IDs. The application validates source IDs and attaches citations; forced JSON grammar is not used on the legacy runtime.
5. Internal streamed JSON must not displace the rendered terminal answer. Knowledge terminal messages are marked and preferred before the common output validation step; internal structures never enter customer text.
6. Added a conservative check for the specifically reproduced reversal of the source's opened-product exception. This is not a general semantic-entailment verifier or a guarantee that every possible model statement is correct.

## Verification commands

From `ai-service`:

```powershell
python -m pytest -q --tb=short -W ignore::DeprecationWarning
```

**571 passed.** Tests include wire-level HTTP payload inspection, streamed JSON finalization, malformed source IDs, document-copy bypasses, cancellation, timeouts, cross-chunk conditions and known policy contradiction cases.

From the repository root:

```powershell
python -m pytest eval/tests tests/test_secret_hygiene.py -q --tb=short -W ignore::DeprecationWarning
```

**32 passed.** Modified-file whitespace validation and production YAML checks also passed.

## Effective production configuration

- `KB_RESPONSE_MODE=generate`
- `KB_ANSWER_TIMEOUT_S=60`
- `KB_ANSWER_MAX_TOKENS=512`
- `KB_LEGACY_MAX_TOKENS=true`
- `KB_CONTEXT_MAX_CHARS=3600`

The generation deadline does not include retrieval/loading time. CPU policy answers can still take tens of seconds; this release is not an instant-response, load-test or concurrency SLA acceptance.

## Preservation and rollback

- The previous image is retained under `aimall-rollback-ai-service:kb-84cf0c6`.
- Private release records include the previous commit/image, previous Compose file, unchanged-container IDs, source hashes and a permission-restricted database backup.
- Failed candidates were blocked or rolled back; they were not left serving production.
- Rollback must restore only the AI image/config and wait for health. Preserve all volumes and other services; do not use reset/clean or `docker compose down -v`.
- Release proof, backup data, credentials and origin-address details are kept outside tracked source. This report intentionally does not contain them.
- The cart source commit already present on `dev` was not used to rebuild or replace the frontend during this AI-only release.
- Existing conversation history was preserved. New replies use the fix; old stored document-dump messages are not rewritten.
