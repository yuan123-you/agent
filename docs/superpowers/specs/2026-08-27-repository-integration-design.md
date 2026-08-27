# Repository Integration and GitHub Publication Design

## Objective

Consolidate every local development branch and the approved uncommitted work into one complete `main` branch, retain all meaningful Git history, document how to run and contribute to AI Mall, and publish only project-required files to `https://github.com/yuan123-you/agent`.

## Current state

- The current branch is `codex/real-product-catalog-task1-6` and contains approved uncommitted application changes.
- Six other feature branches and `master` exist in clean linked worktrees.
- `codex/phase2-live-eval`, `codex/phase3-retrieval-optimization`, and `codex/phase4-agent-actions` form a linear chain.
- The target GitHub repository has an empty `main` initial commit and no other remote branches.
- The local repository currently has no configured remote.

## Integration approach

1. Classify untracked files by runtime, source, generated-data, local-only, or secret status.
2. Commit approved application work while excluding local-only files and secrets.
3. Create the integration `main` branch and merge each independent branch head with merge commits. Merging phase 4 includes the phase 2 and phase 3 ancestry.
4. Resolve conflicts surgically: preserve unique behavior from each branch, prefer the newer implementation where both changed the same behavior, and rely on tests rather than wholesale file selection.
5. Merge the remote empty initial commit using ordinary unrelated-history merge handling. Never force-push.

## Repository publication boundary

Publish application source, database migrations, deterministic data required by the application, tests, CI, Docker definitions, and user/developer documentation. Exclude credentials, `.env`, logs, caches, build artifacts, virtual environments, IDE metadata, linked worktrees, one-off scratch output, and generated data that is reproducible and not consumed at runtime.

## Documentation and standards

- Update `README.md` to accurately describe the merged functionality, supported startup paths, environment setup, validation commands, and security notes.
- Add `CONTRIBUTING.md` with concise branch, commit, testing, secret-handling, and generated-data rules.
- Update `.gitignore` only for concrete local artifacts found during the audit.
- Keep the existing GitHub Actions workflow and do not add a license without an explicit license choice from the owner.

## Verification

Run backend tests, frontend tests/typecheck/build, AI service tests, evaluation generation/baseline, Docker Compose configuration validation, and feasible image builds/smoke checks. Inspect the final tracked-file list, large files, common secret patterns, clean working tree, branch reachability, and remote `main` after push.

## Safety

- Preserve the approved uncommitted work.
- Do not delete linked worktrees or local branches.
- Do not push feature branches.
- Do not commit `.env` or expose credential values in logs or documentation.
- Do not force-push or rewrite existing history.
