# OpenCodeReview-informed full-tree audit and repair plan

**Goal:** Research Alibaba OpenCodeReview's actual implementation and apply evidence-first, standards/spec review to the complete current AI Mall source tree; repair confirmed defects with regression tests.

**Pinned baselines:** AI Mall HEAD `ac4d87015dcba66ea0f7cbd917b1d88eefaf5ed0` plus current uncommitted/untracked work; Alibaba reference `375f64cd6f67a48a135da83cfcf59c52669a09cb`. Coverage manifest: `docs/audits/2026-10-28-audit-manifest.json`.

**Constraints:** No resets, destructive cleanup, commits/pushes, live database writes, secret reads, remote source uploads or external CLI installation. Preserve other ongoing changes. Only fix reproducible correctness, authorization, data consistency and operational defects; do not refactor cosmetic smells.

## Execution
- [x] Read reference orchestration, rules, full-file selection, verification and data-boundary source. Document pinned primary evidence and what was/was not executed.
- [x] Independent Standards and Spec audits, retaining separate evidence and explicit exclusions.
- [x] Establish current frontend types/tests/build, backend tests, AI tests and tooling/config baselines without requiring production services.
- [x] Reproduce HTTP binary-response/type-boundary corruption and stale-session replay races; repair request facade without breaking envelope/error/caching/refresh behavior.
- [x] Triage independent backend/AI/deployment findings; assign non-overlapping fixes only after confirmation from code/tests. Track each accepted/rejected/deferred candidate.
- [x] Run focused red/green tests for every repair, then the full verification matrix. Re-review patched seams and update documentation where contracts change.
- [x] Final report: source research, coverage, Standards findings, Spec findings, actual fixes, verification results and remaining risks/limitations. No claims of exhaustive bug elimination.

## Verified outcome
- Backend 773 / frontend 473 / AI 449 / deterministic tooling 232: all passed.
- Frontend type check and production build, backend package: passed.
- One Standards wrong-order hypothesis was downgraded after the real unique DB constraint disproved its stated consequence; cache identity was still narrowed for robustness.
- Full report and deployment/data caveats: `docs/audits/2026-10-28-open-code-review-audit.md`. No production operations or additional provider uploads performed.
