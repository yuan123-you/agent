# Repository Integration and GitHub Publication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a verified, documented, consolidated `main` branch and publish it safely to `https://github.com/yuan123-you/agent`.

**Architecture:** Preserve existing branch history through ordinary merge commits, using the current catalog branch as the integration seed and merging only independent branch tips. Keep publication scope enforced through `.gitignore`, explicit staging, verification, and a final remote audit.

**Tech Stack:** Git, PowerShell, Vue 3/TypeScript/Vite/Vitest, Java 17/Spring Boot/Maven, Python/pytest, Docker Compose, GitHub Actions

**Spec:** `docs/superpowers/specs/2026-08-27-repository-integration-design.md`

## Global Constraints

- Include the user-approved uncommitted functional changes.
- Exclude credentials, local environments, caches, logs, worktrees, and build artifacts.
- Preserve all meaningful local branch history without force-push or history rewriting.
- Push only the consolidated `main` branch.
- Do not add a software license without an explicit owner choice.

---

### Task 1: Classify and checkpoint the approved working tree

**Files:**
- Modify: `.gitignore`
- Add/modify: only approved application source, migrations, required deterministic data, and runtime scripts reported by `git status`

- [ ] Inspect every untracked file and every diff summary.
- [ ] Add concrete local-only artifacts to `.gitignore` without broad patterns that hide source files.
- [ ] Run focused tests covering the current modified backend scripts, AI ingestion, and frontend stores/components.
- [ ] Stage files explicitly and verify `.env`, logs, caches, `.worktrees`, `Docker`, and `local` are absent.
- [ ] Commit the approved checkpoint with a descriptive conventional commit.

### Task 2: Build the consolidated main history

**Files:**
- Modify: conflict-dependent application and test files only

- [ ] Create `main` from the checkpointed current branch.
- [ ] Merge `master`, `codex/phase4-agent-actions`, `codex/real-product-catalog`, `feature/admin-users-dashboard`, and `feature/t10-rag-retrieval` one at a time with merge commits.
- [ ] For each conflict, inspect base/ours/theirs and preserve unique behavior with the smallest resolution.
- [ ] After each merge, run tests targeted at the affected subsystem and commit the merge.
- [ ] Verify every local branch tip is an ancestor of `main`.

### Task 3: Update publication documentation and standards

**Files:**
- Modify: `README.md`
- Create: `CONTRIBUTING.md`
- Modify: `.gitignore`
- Retain: `.github/workflows/ci.yml`

- [ ] Reconcile README functionality and commands against the merged manifests, Docker files, and CI workflow.
- [ ] Document prerequisites, safe environment setup, Docker/local startup, tests, repository structure, and security boundaries.
- [ ] Add concise contribution rules covering branches, commits, validation, secrets, and generated data.
- [ ] Confirm all Markdown links resolve to tracked paths.
- [ ] Commit the documentation and repository standards.

### Task 4: Run the release verification matrix

**Files:**
- No intended source changes; failures require diagnosis before surgical fixes.

- [ ] Run `mvn -B test` in `backend`.
- [ ] Run `npm test`, `npx tsc --noEmit`, and `npm run build` in `frontend`.
- [ ] Run `pytest -q` in `ai-service`.
- [ ] Generate and run the offline evaluation baseline in `eval`.
- [ ] Run `docker compose config` and build/smoke checks supported by the local environment.
- [ ] Scan tracked files for secrets, oversized files, temporary artifacts, and unresolved conflict markers.
- [ ] Confirm `git status` is clean and all local branches are reachable from `main`.

### Task 5: Integrate and publish the GitHub main branch

**Files:**
- Git remote metadata and merge history only

- [ ] Add `origin` for `https://github.com/yuan123-you/agent.git` and fetch it.
- [ ] Merge `origin/main` with `--allow-unrelated-histories`, preserving its initial commit.
- [ ] Re-run fast final verification and inspect the exact outgoing commit/file set.
- [ ] Push local `main` to `origin/main` without force.
- [ ] Query the remote HEAD and contents to verify publication.
