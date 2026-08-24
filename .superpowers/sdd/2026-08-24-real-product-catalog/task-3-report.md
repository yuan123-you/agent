# Task 3 Report — Normalization, Validation, and Deduplication

## Status
Complete.

## Files
- `backend/scripts/product_catalog/model.py`
- `backend/scripts/product_catalog/normalize.py`
- `backend/scripts/tests/product_catalog/test_normalize.py`

## Commit
`feat: normalize and deduplicate catalog products`

## RED-GREEN
- **RED:** `python -m pytest backend/scripts/tests/product_catalog/test_normalize.py -q` failed during collection with `ModuleNotFoundError: No module named 'backend.scripts.product_catalog.normalize'`.
- **RED (edge case):** malformed URL test failed because `urlsplit(...).port` raised `ValueError`.
- **RED (disallowed scheme):** an `ftp://` source URL was canonicalized before validation; the added regression test failed until the URL gate was tightened.
- **GREEN:** focused suite passed: `6 passed`; full product-catalog regression passed: `47 passed`.

## Concerns
- Category inference is deliberately conservative. An unrecognized hint or product name remains uncategorized and is rejected by `validation_errors` rather than being guessed.
- Origin, material, and production date are cleaned only when supplied and otherwise remain `null`; no factual fields are invented.


## Fix Round 1 — RED-GREEN
- **RED:** `python -m pytest backend/scripts/tests/product_catalog/test_normalize.py -q` produced three expected failures: Mapping specs were not normalized, credential-bearing source URLs were canonicalized into altered provenance, and `Cabbage` matched the `bag` substring.
- **RED (disallowed scheme):** an `ftp://` source URL was canonicalized before validation; the added regression test failed until the URL gate was tightened.
- **GREEN:** Mapping inputs are recursively converted to JSON-compatible dictionaries; strict `json.dumps(..., allow_nan=False)` rejects sets and non-finite numbers; credential-bearing and non-HTTP source URLs remain untouched for validation rejection; category inference uses Unicode-normalized word/phrase boundaries.
- **Verification:** focused suite passed: `9 passed`; full product-catalog regression passed: `50 passed`.


## Fix Round 2 — RED-GREEN
- **RED:** `python -m pytest backend/scripts/tests/product_catalog/test_normalize.py backend/scripts/tests/product_catalog/test_model.py -q` failed for `http://@…` because empty userinfo was erased by canonicalization, and for direct `CatalogProduct` construction because `MappingProxyType` was rejected before serialization.
- **GREEN:** URL authority checks use `is not None` for both username and password, preserving all userinfo-bearing provenance for rejection. Final catalog serialization recursively materializes Mapping/list/tuple values before strict `allow_nan=False` JSON validation and output.
- **Verification:** focused suites passed: `26 passed`; full product-catalog regression passed: `53 passed`.
