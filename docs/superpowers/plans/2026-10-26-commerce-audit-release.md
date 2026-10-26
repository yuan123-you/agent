# Commerce Audit Release Plan — 2026-10-26

**Goal:** Push and deploy the verified commerce audit fixes, then retest the deployed release.

**Scope:** Only audit-owned paths. Preserve concurrent uncommitted assistant/chat/navigation work. Deploy current dev branch without force push, reset/clean, deleting volumes, or changing shared sites.

- [ ] Confirm local/remote Git status and deploy target; inspect existing release procedure.
- [ ] Stage an explicit audit file allowlist and verify a clean exported commit snapshot, not unrelated working-tree changes.
- [ ] Run backend/frontend/AI regression checks and production subpath build for that snapshot.
- [ ] Commit and push dev; verify remote commit identity.
- [ ] Acquire the server deployment lock; preserve previous commit/images and a private DB backup.
- [ ] Build the three application images before stopping services. Drain/stop backend ingress and AI workers together, then start the matched release and wait for health.
- [ ] Verify served asset identity, public page/API/security boundaries, health, and controlled test-account commerce behavior without modifying existing users' data.
- [ ] Record exact release SHA, test results, rollback evidence, limitations, and any remaining failures; do not declare successful deployment based only on container startup.

**Rollback:** Restore recorded application image tags/previous code if startup or core smoke checks fail; preserve all database/Redis/MinIO/Milvus/model volumes and unrelated services. No schema migration is introduced by this release.
