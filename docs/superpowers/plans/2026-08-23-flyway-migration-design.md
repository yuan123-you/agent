# Flyway Migration Design

**Goal:** Make Flyway the single owner of the AI Mall MySQL schema while allowing empty databases and databases already upgraded through the former V2 script to start safely.

## Decisions

- Move the current final schema into `classpath:db/migration/V1__baseline.sql`.
- Preserve all 14 tables currently required by the application, including the former V2 `product.version` and `user_address` changes.
- Enable `baseline-on-migrate` at baseline version 2. Empty schemas execute V1; non-empty legacy schemas without Flyway history are marked as already upgraded through legacy V2 and begin with V3.
- Reserve V2 and begin all future migrations at V3 so a legacy schema is never asked to rerun the consolidated baseline.
- Remove the MySQL docker-entrypoint SQL mount; the MySQL image creates only the database and Flyway creates or upgrades its objects.
- Validate migrations on startup and keep `flyway_schema_history` as the audit record.

## Existing database prerequisite

A non-empty database adopted through `baseline-on-migrate` must already represent the former V2 final schema. Flyway cannot safely infer arbitrary partially applied legacy SQL. Such databases are baselined at version 2; subsequent `V3__...` migrations are then applied normally.
