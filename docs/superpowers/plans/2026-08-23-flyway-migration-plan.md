# Flyway Database Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce auditable Flyway migrations and remove competing Docker entrypoint schema initialization.

**Architecture:** Spring Boot runs Flyway before application data access. A consolidated V1 contains the current 14-table final schema, empty databases execute it, and legacy non-empty databases are adopted at baseline version 2 so future changes start at V3.

**Tech Stack:** Java 17, Spring Boot 3.3.5, Maven, Flyway, MySQL 8, Docker Compose, JUnit 5

**Spec:** `docs/superpowers/plans/2026-08-23-flyway-migration-design.md`

## Global Constraints

- Flyway is the only schema owner.
- Preserve the current 14-table schema and seed data.
- Do not rerun legacy DDL or seed inserts on existing non-empty databases.
- All future migrations start with `V3__`.
- `flyway_schema_history` must remain enabled and validated.

---

### Task 1: Migration contract

**Files:**
- Create: `backend/src/test/java/com/aimall/backend/migration/FlywayMigrationContractTest.java`

- [ ] Write tests requiring the Flyway dependency/configuration, one V1 baseline resource, 14 tables, no database-selection statements, and no Docker entrypoint SQL mount.
- [ ] Run the focused test and observe failure because the migration resource/configuration do not yet exist.

### Task 2: Flyway ownership

**Files:**
- Modify: `backend/pom.xml`
- Modify: `backend/src/main/resources/application.yml`
- Create: `backend/src/main/resources/db/migration/V1__baseline.sql`
- Delete: `backend/src/main/resources/db/init/V1__init.sql`
- Delete: `backend/src/main/resources/db/init/V2__upgrade.sql`
- Modify: `docker-compose.yml`

- [ ] Add Flyway core and MySQL runtime support.
- [ ] Configure location, baseline version 2, baseline-on-migrate, and validation.
- [ ] Move the final schema to V1 baseline and remove `CREATE DATABASE`/`USE` statements.
- [ ] Remove Docker entrypoint migration mounting.
- [ ] Run the focused contract test and observe it pass.

### Task 3: Verification

- [ ] Run the complete backend test suite.
- [ ] Run a clean backend package build.
- [ ] Inspect the final changes against every acceptance criterion.
