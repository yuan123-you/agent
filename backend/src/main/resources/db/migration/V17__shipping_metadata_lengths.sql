-- SPEC-07: align persistent shipping metadata with the validated operator-input bounds.
-- Preserve existing values/nullability; do not change already-published V1/V11 migrations.
ALTER TABLE order_info MODIFY COLUMN logistics_no VARCHAR(100) NULL;
ALTER TABLE order_info MODIFY COLUMN delivery_company VARCHAR(80) NULL;
