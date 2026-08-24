# Real Product Catalog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace 512 fictional products in place and add 2,000 real products, yielding exactly 2,512 auditable products with local compressed images.

**Architecture:** A Python batch pipeline discovers post-2025 public product records through Common Crawl and public structured pages, extracts schema.org Product data, validates and normalizes it, processes images, and emits deterministic JSONL plus audit reports. Flyway adds provenance fields; a transactional importer uploads content-addressed images to MinIO, updates IDs 1–512, and inserts 2,000 rows. Spring remains the product/image serving boundary.

**Tech Stack:** Python 3.11+, requests, warcio, Pillow, PyMySQL, MinIO SDK, pytest; Java 17, Spring Boot 3.3, MyBatis-Plus, Flyway, JUnit 5, MySQL 8, MinIO.

**Spec:** `docs/superpowers/specs/2026-08-24-real-product-catalog-design.md`

## Global Constraints

- Exactly 2,512 active products: update existing IDs 1–512 and insert 2,000.
- Source update or successful collection time is at least `2025-01-01T00:00:00Z`.
- Every record has real name, brand, positive public reference price, currency, source identity/URL, valid specs JSON, and decodable local image.
- Never bypass authentication, CAPTCHA, access controls, robots exclusions, or rate limits; never fabricate product facts.
- Unknown origin, material, and production date remain null. Deterministic demo `stock`/`sales` are labeled simulated.
- Images: longest edge ≤1200 px; opaque WebP quality 82; transparent lossless WebP; retain a smaller supported original.
- Do not commit image/cache binaries. Any hard validation failure prevents cutover.

## File Map

- `backend/scripts/product_catalog/{model,config,commoncrawl,jsonld,normalize,images,catalog,importer}.py`: focused pipeline modules.
- `backend/scripts/generate_product_catalog.py`: discover/build/upload/import/verify CLI.
- `backend/scripts/product_sources.json`, `requirements-product-catalog.txt`: runtime inputs.
- `backend/scripts/tests/product_catalog/`: module tests and fixtures.
- `backend/src/main/resources/product-catalog/{products.jsonl,catalog-report.json,catalog-report.md}`: committed outputs.
- `backend/src/main/resources/db/migration/V6__product_catalog_provenance.sql`: schema extension.
- `Product.java`, `ProductImageService.java`, `ProductImageController.java`: provenance and image serving.
- `.gitignore`, `README.md`: cache exclusions and operations guide.

---

### Task 1: Record Contract and Source Configuration

**Files:** Create `backend/scripts/product_catalog/{__init__,model,config}.py`, `backend/scripts/product_sources.json`, `backend/scripts/requirements-product-catalog.txt`; test in `backend/scripts/tests/product_catalog/test_{model,config}.py`.

**Interfaces:** Produces `RawProduct`, `CatalogProduct`, `ImageCandidate`, `SourceConfig`, `load_source_config(Path) -> SourceConfig`; `CatalogProduct.to_json() -> dict`.

- [ ] Write failing tests proving `Decimal("7999.00")` serializes as `"7999.00"`, UTC time as `2025-07-01T00:00:00Z`, specs remain objects, null optional facts remain null, and simulation marker is true.
- [ ] Run `python -m pytest backend/scripts/tests/product_catalog/test_model.py backend/scripts/tests/product_catalog/test_config.py -q`; expect import failure.
- [ ] Implement frozen dataclasses and strict config parsing. Stable categories are `PHONE,DIGITAL,COMPUTER,APPLIANCE,HOME_DECOR,FURNITURE,CLOTHING,SHOES,BAGS,BEAUTY,PERSONAL_CARE,FOOD,FRESH,MATERNAL,TOYS,SPORTS,BOOK,CAR,PET,HEALTH,JEWELRY`.
- [ ] Configure `CC-MAIN-2025-30`, minimum time `2025-01-01T00:00:00Z`, conservative rate/candidate limits, and domains `apple.com,samsung.com,lenovo.com,hp.com,dell.com,asus.com,ikea.com,lego.com,nike.com,adidas.com,sephora.com,ulta.com,decathlon.com,petsmart.com,bookshop.org,bestbuy.com,target.com,walmart.com,homedepot.com`; blocked domains are skipped.
- [ ] Pin `requests==2.32.5`, `warcio==1.7.5`, `Pillow==11.3.0`, `PyMySQL==1.1.2`, `minio==7.2.16`, `pytest==8.4.1`.
- [ ] Re-run focused tests; expect PASS. Commit: `git commit -am "feat: define real product catalog contract"` after explicitly adding new files.

### Task 2: Common Crawl Discovery and JSON-LD Extraction

**Files:** Create `commoncrawl.py`, `jsonld.py`, tests `test_commoncrawl.py`, `test_jsonld.py`, fixture `fixtures/product_page.html`.

**Interfaces:** `discover_records(source, cache_dir) -> Iterator[CrawlRecord]`; `fetch_warc_html(record, session) -> str`; `extract_products(html, source_url, collected_at, source_name) -> list[RawProduct]`.

- [ ] Add a fixture containing malformed JSON-LD followed by a valid `@graph` Product with Brand, images, Offer price/currency/SKU, description, and additionalProperty. Tests assert malformed data is skipped and valid fields are exact.
- [ ] Add a mocked Common Crawl index/range test asserting cache use, byte Range, response cap, UTC timestamp, and per-source candidate limit.
- [ ] Run both tests; expect missing-module failure.
- [ ] Query `https://index.commoncrawl.org/{index}-index` with `url=*.{domain}/*`, JSON output, status 200, HTML MIME, and URL-key collapse. Cache by request SHA-256.
- [ ] Fetch declared `filename/offset/length` from `https://data.commoncrawl.org/`; decode only the requested WARC record with `ArchiveIterator`; enforce timeout/size/rate limits.
- [ ] Parse only `script[type=application/ld+json]` using `HTMLParser`; support object/list/`@graph`, Product type arrays, offer object/list, and choose lowest available positive price. Reject missing brand, currency, source ID, or images.
- [ ] Run both tests; expect PASS. Commit `feat: discover public product jsonld records`.

### Task 3: Normalization, Validation, and Deduplication

**Files:** Create `normalize.py`; test `test_normalize.py`.

**Interfaces:** `normalize(raw, category_hint) -> CatalogProductCandidate`; `deduplicate(items) -> list`; `validation_errors(item, minimum_time) -> list[str]`.

- [ ] Write failing tests for HTML/whitespace cleanup, Unicode preservation, two-decimal price, URL normalization, category mapping, invalid currency, pre-2025 rejection, duplicate SKU, duplicate normalized brand/model, and null unknown facts.
- [ ] Run the test; expect missing functions.
- [ ] Implement NFKC/case-folded comparison while preserving display text. Use explicit source hint before keyword mapping. Validate when either source-updated or collected time meets the minimum.
- [ ] Derive demo values only from the unique-key hash: `stock=10+seed%491`, `sales=50+seed%9951`, where `seed=int(sha256(key)[:8],16)`; set `simulated_commerce_fields=true`.
- [ ] Run test; expect PASS. Commit `feat: normalize and deduplicate catalog products`.

### Task 4: Safe Image Processing and MinIO Storage

**Files:** Create `images.py`; test `test_images.py` plus opaque/transparent fixtures.

**Interfaces:** `process_image(data, content_type) -> ProcessedImage`; `download_image(url, session, settings) -> DownloadedImage`; `upload_image(image, client, bucket) -> str`. Result exposes hash, extension, MIME, dimensions, original/output byte counts, and payload.

- [ ] Write failing tests: 1600×800 becomes ≤1200×600; alpha survives; EXIF orientation is applied; SVG, >10 MiB response, and >40M decoded pixels fail; hash is stable; smaller JPEG/PNG is retained.
- [ ] Run `python -m pytest backend/scripts/tests/product_catalog/test_images.py -q`; expect missing functions.
- [ ] Implement `ImageOps.exif_transpose`, Lanczos thumbnail, RGB WebP quality 82/method 6, RGBA lossless/method 6, metadata stripping, JPEG/PNG/WebP allowlist, timeout/redirect/byte/pixel caps.
- [ ] Store as `product-images/catalog/{sha256}.{ext}` and expose `/api/v1/product-images/catalog/{sha256}.{ext}`. Use `stat_object` to skip an identical existing object; never log credentials.
- [ ] Run test; expect PASS. Commit `feat: compress and store catalog images`.

### Task 5: Deterministic Catalog and Reports

**Files:** Create `catalog.py`; test `test_catalog.py`.

**Interfaces:** `select_catalog(items,total=2512,replacement_count=512) -> list[CatalogProduct]`; `write_catalog(items,output_dir) -> CatalogReport`; `verify_catalog(path,report_path) -> VerificationResult`.

- [ ] Build 2,520 test records across all category codes. Assert exactly 2,512 stable records after shuffled input, unique source keys/content hashes, valid prices/images/times, and replacement slots 1–512 only.
- [ ] Run test; expect missing functions.
- [ ] Sort by category/brand/name/source/source-ID, then round-robin categories to limit domination; assign slots 1–512. Write UTF-8 JSONL with sorted keys and final newline.
- [ ] Make verification fail unless every Global Constraint passes. JSON/Markdown reports contain source/category/rejection counts, duplicates, image failures, bytes before/after/saved/percentage, WebP/retained-original counts, and `simulated_fields=["stock","sales"]`.
- [ ] Run test; expect PASS. Commit `feat: build verified 2512 product catalog`.

### Task 6: Flyway Provenance Schema and Entity

**Files:** Create `V6__product_catalog_provenance.sql`; modify `Product.java`; create `ProductCatalogMigrationTest.java`.

**Interfaces:** Adds `currency`, `source_name`, `source_url`, `source_product_id`, `source_updated_at`, `collected_at`, `original_image_url`, `image_sha256`, `simulated_commerce_fields`; unique `(source_name,source_product_id)`.

- [ ] Write a failing resource/reflection test asserting all columns, `source_url VARCHAR(2048)`, `original_image_url VARCHAR(2048)`, `image_url VARCHAR(512)`, unique source key, collection-time index, and matching camelCase entity fields.
- [ ] Run `cd backend; .\mvnw.cmd -q -Dtest=ProductCatalogMigrationTest test`; expect FAIL.
- [ ] Add nullable provenance columns so V1 rows migrate safely, `simulated_commerce_fields TINYINT NOT NULL DEFAULT 0`, unique source key, and `(collected_at,status)` index. Never edit applied V1.
- [ ] Map strings, `LocalDateTime` timestamps, and Boolean simulation flag in `Product.java`.
- [ ] Run `cd backend; .\mvnw.cmd -q -Dtest=ProductCatalogMigrationTest,AdminProductContractTest test`; expect PASS. Commit `feat: add product catalog provenance schema`.

### Task 7: Transactional Importer

**Files:** Create `importer.py`; test `test_importer.py`.

**Interfaces:** `import_catalog(connection,products,dry_run=False) -> ImportResult`; `verify_database(connection) -> DatabaseVerification`.

- [ ] Write fake-cursor tests proving staging creation/batches, count 2512, updates IDs 1–512, inserts 2,000, removes only the known V1 seeded review rows, preserves orders/favorites/history, rolls back on mismatch, and commits once.
- [ ] Run importer test; expect missing functions.
- [ ] Stage explicit columns with parameterized batches of 100. Pre-cutover assert 2,512 rows/source keys, 512 slots, zero invalid JSON/nonpositive prices/remote or Picsum final URLs.
- [ ] In one transaction update by replacement slot and insert null-slot rows. Use source unique key for refresh idempotency. Refuse initial import unless active pre-count is 512; `--refresh-existing-catalog` requires matching catalog version and must remain 2,512.
- [ ] Run test; expect PASS. Commit `feat: import catalog with transactional cutover`.

### Task 8: Content-Addressed Image HTTP Route

**Files:** Modify `ProductImageService.java`, `ProductImageController.java`, `ProductImageServiceTest.java`; create `ProductImageControllerTest.java`.

**Interfaces:** `loadCatalog(String filename) -> ImageContent`; `GET /api/v1/product-images/catalog/{sha256}.{jpg|png|webp}`.

- [ ] Write failing tests accepting lowercase 64-hex names/extensions and loading `product-images/catalog/<name>`, with correct MIME/cache header; reject uppercase, separators, `..`, UUID names, and unsupported extensions.
- [ ] Run `cd backend; .\mvnw.cmd -q -Dtest=ProductImageServiceTest,ProductImageControllerTest test`; expect FAIL.
- [ ] Add `@GetMapping("/catalog/{filename:.+}")`; validate `[0-9a-f]{64}\\.(jpg|png|webp)`; load only catalog prefix; set `Cache-Control: public,max-age=31536000,immutable`; preserve UUID upload behavior.
- [ ] Re-run tests; expect PASS. Commit `feat: serve content addressed catalog images`.

### Task 9: End-to-End CLI and Safety

**Files:** Create `generate_product_catalog.py`, `test_cli.py`; modify `.gitignore`.

**Interfaces:** Commands `discover`, `build`, `upload-images`, `import`, `verify`, `all`; nonzero exit on hard failure.

- [ ] Write failing CLI tests: help lists commands; build requires cache; import requires verified manifest and `--apply`; verify is read-only; secrets only use `MYSQL_*`/`MINIO_*`; logs redact secrets.
- [ ] Run CLI test; expect missing entry point.
- [ ] Implement default cache `backend/.catalog-cache/{index,warc,images}` and outputs under `backend/src/main/resources/product-catalog/`. `all` stops after upload/verify unless `--apply`; `import --dry-run` never mutates.
- [ ] Ignore `backend/.catalog-cache/`, `*.warc`, `*.warc.gz`, temporary staging files, and `.venv-product-catalog`; do not ignore committed catalog outputs.
- [ ] Run `python -m pytest backend/scripts/tests/product_catalog -q`; expect PASS. Commit `feat: add safe catalog generation cli`.

### Task 10: Generate the Real 2,512-Product Artifact

**Files:** Create `backend/src/main/resources/product-catalog/products.jsonl`, `catalog-report.json`, `catalog-report.md`.

- [ ] Create venv and install: `python -m venv backend/.venv-product-catalog`; `backend/.venv-product-catalog/Scripts/python -m pip install -r backend/scripts/requirements-product-catalog.txt`.
- [ ] Run discovery: `.../python backend/scripts/generate_product_catalog.py discover --config backend/scripts/product_sources.json --minimum-candidates 4000`; require ≥4,000 cached candidates and report blocked sources as skipped.
- [ ] Run `build --target 2512` then `upload-images`; failed images are replaced by validated candidates, never placeholders.
- [ ] Run `verify`; require `count=2512`, `replacement_slots=512`, zero hard errors/Picsum/duplicates/invalid JSON, and compliant times.
- [ ] Inspect at least one record/image per populated category against its source; record sample keys in Markdown report; remove unsupported facts and rebuild.
- [ ] Add only JSONL and reports; commit `data: add verified real product catalog`.

### Task 11: Apply to MySQL and MinIO

**Files:** Runtime state only.

- [ ] Run `docker compose up -d mysql minio` and `docker compose ps mysql minio`; require healthy.
- [ ] Start backend once with `cd backend; .\mvnw.cmd -q -DskipTests spring-boot:run`; require Flyway V6 success and no checksum errors, then stop before exclusive cutover.
- [ ] Run `generate_product_catalog.py import --dry-run`; require pre-count 512, manifest 2512, slots 512, no mutation.
- [ ] Run `generate_product_catalog.py import --apply`; require one transaction updating 512/inserting 2,000 and final count 2,512; any assertion causes transaction rollback.
- [ ] Run `generate_product_catalog.py verify --database --minio`; require 2,512 provenance keys, no Picsum, every object present, MIME matching extension.

### Task 12: Regression, Documentation, and Evidence

**Files:** Modify `README.md`; modify `eval/dataset/products.json` only if AI eval references fictional products.

- [ ] Update README from 512 fictional to 2,512 real products; document freshness rule, WebP settings, commands, dry-run, simulated fields, cache, reports, and recovery.
- [ ] Run `python -m pytest backend/scripts/tests/product_catalog -q`; require PASS.
- [ ] Run `cd backend; .\mvnw.cmd test`; require BUILD SUCCESS.
- [ ] Run `cd frontend; npm test; npm run build`; require tests/build success.
- [ ] Smoke-test list, category, search, replaced ID, new ID, and selected image URLs; require HTTP 200, provenance, positive price, and image MIME. Rebuild AI index and find one known product ID.
- [ ] Run `generate_product_catalog.py verify --database --minio --http-base http://localhost:8080`; require:

```text
products=2512
replacement_slots=512
new_products=2000
hard_errors=0
picsum_urls=0
missing_images=0
invalid_specs=0
duplicate_source_keys=0
```

- [ ] Run `git diff --check`; confirm no secrets/cache/images are tracked. Commit README/eval changes as `docs: document real product catalog workflow`.
- [ ] Completion evidence must state every test outcome, final DB count, source/category counts, bytes before/after, saved percentage, WebP/retained-original/missing counts, and paths to JSONL/reports. Do not claim completion if hard acceptance fails.

