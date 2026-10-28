"""Collect current Apple China SKU facts and content-addressed photographs.

Usage: python -m backend.scripts.collect_official_catalog --output DIR --images DIR
No database credentials or mutations. The cutover is a separate, guarded step.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import time
import requests
from backend.scripts.product_catalog.official_store import parse_product_page, listing_product_urls
from backend.scripts.product_catalog.images import download_image, process_image, DownloadSettings
from backend.scripts.product_catalog.cutover import validate_catalog_images

LISTINGS = ["accessories/all", "iphone/accessories", "ipad/accessories", "mac/accessories",
            "watch/accessories", "accessories/all/headphones-speakers",
            "accessories/all/mice-keyboards", "accessories/all/health-fitness"]


def collect(output, images, minimum=24):
    output, images = Path(output), Path(images)
    output.mkdir(parents=True, exist_ok=True)
    images.mkdir(parents=True, exist_ok=True)
    pages = images.parent / "official-cn-pages"
    pages.mkdir(parents=True, exist_ok=True)
    urls = set()
    with requests.Session() as session:
        for path in LISTINGS:
            response = session.get("https://www.apple.com.cn/shop/" + path, timeout=30)
            response.raise_for_status()
            urls.update(listing_product_urls(response.text))
            time.sleep(.3)
    rejected = []
    def fetch(url):
        with requests.Session() as session:
            try:
                time.sleep(.3)
                response = session.get(url, timeout=30)
                response.raise_for_status()
                (pages / (sha256(url.encode()).hexdigest() + ".html")).write_text(response.text, encoding="utf-8")
                row = parse_product_page(response.text, url)
                downloaded = download_image(row["original_image_url"], session, DownloadSettings(timeout_seconds=30))
                image = process_image(downloaded.payload, downloaded.content_type)
                filename = image.sha256 + "." + image.extension
                (images / filename).write_bytes(image.payload)
                row.update(image_url="/api/v1/product-images/catalog/" + filename,
                           image_sha256=image.sha256, image_original_bytes=image.original_bytes,
                           image_output_bytes=image.output_bytes)
                row["content_hash"] = sha256(json.dumps({k:v for k,v in row.items() if k != "content_hash"},
                    sort_keys=True, ensure_ascii=False).encode()).hexdigest()
                return row
            except Exception as exc:
                rejected.append({"url": url, "error": str(exc)[:200]})
                return None
    with ThreadPoolExecutor(max_workers=3) as pool:
        records = [row for row in pool.map(fetch, sorted(urls)) if row]
    unique = {(p["source_name"], p["source_product_id"]): p for p in records}
    records = sorted(unique.values(), key=lambda p: p["source_product_id"])
    if len(records) < minimum:
        raise ValueError(f"only {len(records)} verified products; require {minimum}")
    verified = validate_catalog_images(records, images)
    (output / "products.jsonl").write_text("".join(json.dumps(p, ensure_ascii=False, sort_keys=True) + "\n" for p in records), encoding="utf-8")
    report = {"source": "www.apple.com.cn", "currency": "CNY", "products": len(records),
              "verified_images": verified, "categories": dict(Counter(p["category"] for p in records)),
              "brands": dict(Counter(p["brand"] for p in records)), "rejected": rejected,
              "commerce_note": "Official reference prices; inventory is demo data, sales start at zero. No source stock, sales, shipping or warranty promises are asserted."}
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--images", required=True)
    parser.add_argument("--minimum", type=int, default=24)
    args = parser.parse_args()
    collect(args.output, args.images, args.minimum)
