"""Extract matching CNY product facts and gallery photographs from Apple China PDPs.

Only public embedded JSON is decoded; no scripts are executed. Unavailable or
unverifiable items are rejected rather than substituted with category artwork.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
from html import unescape
from html.parser import HTMLParser
import json
import re
from urllib.parse import urlsplit

SOURCE = "https://www.apple.com.cn"
IMAGE_HOST = "store.storeimages.cdn-apple.com"


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def _text(html):
    parser = _Text()
    parser.feed(str(html))
    return " ".join(" ".join(parser.parts).split())


def _model(html, name, required=False):
    match = re.search(r"(?:window\.)?pageLevelData\." + re.escape(name) + r"\s*=\s*", html)
    if match:
        try:
            value, _ = json.JSONDecoder().raw_decode(html, match.end())
            if isinstance(value, dict):
                return value
        except (ValueError, TypeError):
            pass
    if required:
        raise ValueError(f"missing official product model: {name}")
    return {}


def listing_product_urls(html):
    # Match both HTML hrefs and JSON model productDetailsUrl values.
    links = re.findall(r'["\']((?:https://www\.apple\.com\.cn)?/shop/product/[^"\'<>\s]+)["\']', html)
    return sorted({SOURCE + urlsplit(unescape(link)).path.lower() for link in links})


def _section_text(model):
    parts = []
    for item in model.get("tiles", {}).get("groups", {}).get("items", []):
        render = item.get("value", {}).get("render", "")
        if render:
            text = _text(render)
            if text:
                parts.append(text)
    return "\n".join(parts)


def parse_product_page(html, url, collected_at=None):
    if urlsplit(url).hostname != "www.apple.com.cn" or not urlsplit(url).path.startswith("/shop/product/"):
        raise ValueError("product source must be an official China product page")
    model = _model(html, "PDPContent", required=True)
    purchase = model.get("purchaseInfo", {})
    price_data = purchase.get("price", {})
    name = _text(model.get("productTitle", ""))
    sku = purchase.get("partNumber", "")
    if not name or len(name) > 128 or not sku or price_data.get("priceCurrency") != "CNY":
        raise ValueError("product requires a name, SKU and explicit CNY price")
    price = Decimal(str(price_data.get("currentPrice", {}).get("raw_amount", "0")))
    if not price.is_finite() or price <= 0:
        raise ValueError("product requires a positive official price")
    if purchase.get("buyNowButton", {}).get("disabled") is not False:
        raise ValueError("official product is not available to purchase")
    gallery = model.get("imageGallery", {}).get("galleryImagesList", {}).get("items", [])
    if not gallery:
        raise ValueError("product has no gallery photograph")
    photo = gallery[0].get("value", {}).get("gallery", {})
    sources = photo.get("sources", [])
    image_url = sources[0].get("srcSet", "") if sources else ""
    parsed = urlsplit(image_url)
    if photo.get("noImage") or parsed.scheme != "https" or parsed.hostname != IMAGE_HOST or not parsed.path.startswith("/1/as-images.apple.com/is/"):
        raise ValueError("gallery image must be the official product photograph")
    specs = {"产品型号": sku}
    compatible = _model(html, "Compatibility").get("compatibleProducts", [])
    names = [item.get("value", {}).get("text", "") for group in compatible
             for item in group.get("products", {}).get("items", [])]
    if names:
        specs["兼容机型"] = "、".join(names)
    for key, label in [("TechSpecs", "技术规格"), ("WhatsInTheBox", "包装内容")]:
        text = _section_text(_model(html, key))
        if text:
            specs[label] = text
    description = _section_text(_model(html, "Overview"))
    if not description:
        raise ValueError("official product overview is missing")
    # Manufacturer is only identified for explicit first-party product families.
    first_party = r"(?:Apple|AirPods|AirTag|MagSafe|妙控|USB-C|雷雳|MagSafe|HomePod|iPhone|iPad|Studio Display|Pro Display|VESA|带支架的 iPhone|适用于 .*i(?:Phone|Pad))"
    brand = "Apple" if re.match(first_party, name, re.I) or re.search(r"妙控键盘|EarPods|智能双面夹", name) else "品牌未提供"
    for manufacturer in ["Belkin", "Beats", "Logitech", "罗技", "Anker", "OtterBox", "Incase", "mophie", "Satechi", "Twelve South", "HidrateSpark", "Elevation Lab", "Kensington", "Tech21", "Bellroy", "Nimble", "MOFT", "Aer", "Blackmagic", "Rains", "Herschel", "Native Union"]:
        if re.search(r"(?<![A-Za-z])" + re.escape(manufacturer), name, re.I):
            brand = manufacturer
            break
    if "Powerbeats" in name:
        brand = "Beats"
    category = "LAPTOP" if re.search(r"Mac|键盘|鼠标|触控板|显示器|雷雳|HDMI|VESA|读卡器|转接器", name, re.I) else "PHONE"
    if re.search(r"背包|斜挎包|收纳包|旅行包|手提包", name):
        category = "BAGS"
    stamp = (collected_at or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    result = dict(name=name, brand=brand, category=category, price=format(price, ".2f"), currency="CNY",
                  description=description, selling_points=[], specs=specs, source_name="www.apple.com.cn",
                  source_url=url, source_product_id=sku, source_updated_at=None, collected_at=stamp,
                  original_image_url=image_url, image_alt=photo.get("alt", ""), origin=None, material=None,
                  production_date=None, stock=100, sales=0, commerce_values_simulated=True,
                  replacement_slot=None, catalog_version="official-cn-2026-10-28")
    result["content_hash"] = sha256(json.dumps(result, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return result
