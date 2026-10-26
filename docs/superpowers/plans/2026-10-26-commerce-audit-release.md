# Commerce Audit Release Plan — 2026-10-26

**Goal:** Push and deploy the verified commerce audit fixes, then retest the deployed release.

**Scope:** Only audit-owned paths. Preserve concurrent uncommitted assistant/chat/navigation work. Deploy current dev branch without force push, reset/clean, deleting volumes, or changing shared sites.

- [x] Confirm local/remote Git status and deploy target; inspect existing release procedure.
- [x] Stage an explicit audit file allowlist and verify a clean exported commit snapshot, not unrelated working-tree changes.
- [x] Run backend/frontend/AI regression checks and production subpath build for that snapshot.
- [x] Commit and push dev; verify remote commit identity.
- [x] Acquire the server deployment lock; preserve previous commit/images and a private DB backup.
- [x] Build the three application images before stopping services. Drain/stop backend ingress and AI workers together, then start the matched release and wait for health.
- [x] Verify served asset identity, public page/API/security boundaries, health, and controlled test-account commerce behavior without modifying existing users' data.
- [x] Record exact release SHA, test results, rollback evidence, limitations, and any remaining failures; do not declare successful deployment based only on container startup.

**Rollback:** Restore recorded application image tags/previous code if startup or core smoke checks fail; preserve all database/Redis/MinIO/Milvus/model volumes and unrelated services. No schema migration is introduced by this release.

**Verified outcome:** application commit 5d70e00; backend677/frontend258/AI269/safety19; live business checks41; deployment/read-only checks32; real AI SSE11.6s; all9 services healthy. Separate concurrent work remains uncommitted and unshipped.
