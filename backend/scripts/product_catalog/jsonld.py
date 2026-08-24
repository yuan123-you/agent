"""Extract schema.org Product facts from JSON-LD script blocks only."""
from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from typing import Any, Iterator

from .model import ImageCandidate, RawProduct


class _JsonLdScriptParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._inside_jsonld = False
        self._parts: list[str] = []
        self.scripts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "script" and dict(attrs).get("type", "").lower() == "application/ld+json":
            self._inside_jsonld = True
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._inside_jsonld:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._inside_jsonld:
            self.scripts.append("".join(self._parts))
            self._inside_jsonld = False
            self._parts = []


def _nodes(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, list):
        for item in value:
            yield from _nodes(item)
    elif isinstance(value, dict):
        graph = value.get("@graph")
        if graph is not None:
            yield from _nodes(graph)
        else:
            yield value


def _is_product(node: dict[str, Any]) -> bool:
    types = node.get("@type")
    if isinstance(types, str):
        types = [types]
    return isinstance(types, list) and any(
        isinstance(item, str) and item.rsplit("/", 1)[-1] == "Product" for item in types
    )


def _text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _brand(value: Any) -> str | None:
    if isinstance(value, dict):
        return _text(value.get("name"))
    return _text(value)


def _images(value: Any) -> tuple[ImageCandidate, ...]:
    values = value if isinstance(value, list) else [value]
    urls: list[ImageCandidate] = []
    for image in values:
        url = _text(image.get("url")) if isinstance(image, dict) else _text(image)
        if url:
            urls.append(ImageCandidate(url))
    return tuple(urls)


def _available_offer(offer: dict[str, Any]) -> tuple[Decimal, str] | None:
    availability = _text(offer.get("availability"))
    if availability and availability.rsplit("/", 1)[-1] == "OutOfStock":
        return None
    try:
        price = Decimal(str(offer.get("price")))
    except (InvalidOperation, ValueError):
        return None
    currency = _text(offer.get("priceCurrency"))
    return (price, currency) if price.is_finite() and price > 0 and currency else None


def _offer(node: dict[str, Any]) -> tuple[Decimal, str] | None:
    offers = node.get("offers")
    options = offers if isinstance(offers, list) else [offers]
    available = [result for item in options if isinstance(item, dict) and (result := _available_offer(item))]
    return min(available, key=lambda value: value[0]) if available else None


def _specs(value: Any) -> dict[str, Any]:
    values = value if isinstance(value, list) else [value]
    result: dict[str, Any] = {}
    for item in values:
        if not isinstance(item, dict):
            continue
        name = _text(item.get("name"))
        item_value = item.get("value")
        if name and isinstance(item_value, (str, int, float, bool)):
            result[name] = item_value
    return result


def extract_products(html: str, source_url: str, collected_at: datetime, source_name: str) -> list[RawProduct]:
    """Return valid raw Products from JSON-LD, never from rendered page text."""
    parser = _JsonLdScriptParser()
    parser.feed(html)
    parser.close()
    products: list[RawProduct] = []
    for script in parser.scripts:
        try:
            payload = json.loads(script)
        except json.JSONDecodeError:
            continue
        for node in _nodes(payload):
            if not _is_product(node):
                continue
            name = _text(node.get("name"))
            brand = _brand(node.get("brand"))
            images = _images(node.get("image"))
            source_product_id = _text(node.get("sku"))
            offer = _offer(node)
            if not (name and brand and images and source_product_id and offer):
                continue
            price, currency = offer
            products.append(RawProduct(
                name=name,
                brand=brand,
                category=None,
                price=price,
                currency=currency,
                description=_text(node.get("description")),
                selling_points=(),
                specs=_specs(node.get("additionalProperty")),
                source_name=source_name,
                source_url=source_url,
                source_product_id=source_product_id,
                source_updated_at=None,
                collected_at=collected_at,
                image_candidates=images,
            ))
    return products