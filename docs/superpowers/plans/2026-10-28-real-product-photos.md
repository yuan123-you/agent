# Verified product photographs and safe catalog cutover

**Goal:** Replace the known demonstration catalog with traceable, CNY-priced real products and verified local raster photographs, without changing merchant products or historical records.
**Architecture:** Add a focused official-store collector and a guarded append-and-retire importer alongside the existing 2512-row importer. Do not edit applied Flyway migrations. Persist a reproducible manifest, verify every referenced image object before cutover, and retain old product IDs.
**Spec:** User confirmed replacing demonstration entries with corresponding real products while preserving merchant entries and historical orders.
**Constraints:** Do not use generated photographs, category illustrations or unrelated stock imagery. Never coerce foreign prices to CNY. Keep credentials, backups and source HTML private. Preserve concurrent frontend changes.

- [x] Reproduce: reject SVG/category placeholders; test source parsing (matching name, price, SKU, photo, actual specifications), subpath image resolution, and exact seed identity guards.
- [x] Collect: read CNY official product pages; fail closed on missing price/photo/source, store exact-source facts and content hashes; download/decode photographs and upload content-addressed files.
- [x] Implement append-and-retire cutover: exact known seed allowlist, transaction, dry run, full image/provenance validation, taxonomy linkage, preserve merchant/order/review/cart data, no old ID reuse.
- [x] Verify locally: red/green targeted tests, catalog tests, relevant frontend/build checks; back up production DB and protected-record digests before dry run/apply.
- [x] Deploy: publish only task-owned changes, upload verified images, transactionally apply, check every photograph via public API/hash/decode and review desktop/mobile home/search/detail visually. Record measured results and rollback instructions.
