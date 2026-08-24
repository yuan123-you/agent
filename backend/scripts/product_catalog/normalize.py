"""Normalization, quality validation, and duplicate rejection for catalog products."""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal, ROUND_HALF_UP
from html.parser import HTMLParser
import json
import re
from typing import Any, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .model import CATEGORIES, CatalogProductCandidate, RawProduct

_CENTS = Decimal("0.01")
_CURRENCIES = frozenset("""
AED AFN ALL AMD ANG AOA ARS AUD AWG AZN BAM BBD BDT BGN BHD BIF BMD BND BOB BOV BRL BSD BTN BWP
BYN BZD CAD CDF CHE CHF CHW CLF CLP CNY COP COU CRC CUP CVE CZK DJF DKK DOP DZD EGP ERN ETB EUR
FJD FKP GBP GEL GHS GIP GMD GNF GTQ GYD HKD HNL HRK HTG HUF IDR ILS INR IQD IRR ISK JMD JOD JPY
KES KGS KHR KMF KPW KRW KWD KYD KZT LAK LBP LKR LRD LSL LYD MAD MDL MGA MKD MMK MNT MOP MRU MUR
MVR MWK MXN MXV MYR MZN NAD NGN NIO NOK NPR NZD OMR PAB PEN PGK PHP PKR PLN PYG QAR RON RSD RUB
RWF SAR SBD SCR SDG SEK SGD SHP SLE SLL SOS SRD SSP STN SVC SYP SZL THB TJS TMT TND TOP TRY TTD
TWD TZS UAH UGX USD USN UYI UYU UYW UZS VED VES VND VUV WST XAF XCD XCG XOF XPF YER ZAR ZMW ZWG
""".split())
_CATEGORY_TERMS = (
    ("PHONE", ("smartphone", "cell phone", "mobile phone", "iphone", "android phone", "phone")),
    ("COMPUTER", ("laptop", "notebook", "macbook", "desktop", "chromebook", "computer")),
    ("DIGITAL", ("headphone", "headphones", "earphone", "earphones", "earbud", "earbuds", "camera", "speaker", "television", "tv")),
    ("APPLIANCE", ("refrigerator", "washing machine", "vacuum", "microwave", "air conditioner")),
    ("HOME_DECOR", ("lamp", "rug", "curtain", "mirror", "decor")),
    ("FURNITURE", ("chair", "table", "sofa", "bed", "desk", "cabinet")),
    ("CLOTHING", ("shirt", "jacket", "dress", "pants", "jeans", "hoodie")),
    ("SHOES", ("shoe", "sneaker", "boot", "sandal")),
    ("BAGS", ("bag", "backpack", "handbag", "luggage")),
    ("BEAUTY", ("makeup", "lipstick", "foundation", "mascara")),
    ("PERSONAL_CARE", ("shampoo", "toothbrush", "deodorant", "razor")),
    ("FOOD", ("coffee", "tea", "chocolate", "snack")),
    ("FRESH", ("fresh", "fruit", "vegetable", "meat")),
    ("MATERNAL", ("baby", "diaper", "stroller")),
    ("TOYS", ("toy", "lego", "puzzle", "doll")),
    ("SPORTS", ("bicycle", "bike", "fitness", "yoga", "sports")),
    ("BOOK", ("book", "novel", "paperback", "hardcover")),
    ("CAR", ("automotive", "car ", "tire", "tyre")),
    ("PET", ("pet", "dog", "cat", "aquarium")),
    ("HEALTH", ("vitamin", "supplement", "medical", "health")),
    ("JEWELRY", ("ring", "necklace", "bracelet", "jewelry", "jewellery")),
)
_CATEGORY_ALIASES = {
    "electronics": "DIGITAL", "electronic": "DIGITAL", "audio": "DIGITAL",
    "phones": "PHONE", "mobile": "PHONE", "mobile phones": "PHONE",
    "computers": "COMPUTER", "beauty care": "BEAUTY", "personal care": "PERSONAL_CARE",
    "home decor": "HOME_DECOR", "home decoration": "HOME_DECOR", "fresh food": "FRESH",
    "maternal and baby": "MATERNAL", "books": "BOOK", "cars": "CAR", "pets": "PET",
}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _clean_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    parser = _TextExtractor()
    parser.feed(value)
    parser.close()
    result = " ".join("".join(parser.parts).split())
    return result or None


def _fold(value: str | None) -> str:
    # NFKC is intentionally comparison-only: display/source text is kept intact.
    import unicodedata

    return " ".join(unicodedata.normalize("NFKC", value or "").casefold().split())


def _category(value: str | None) -> str | None:
    folded = _fold(value)
    canonical = folded.replace("-", "_").replace(" ", "_").upper()
    if canonical in CATEGORIES:
        return canonical
    return _CATEGORY_ALIASES.get(folded)


def _keyword_category(name: str | None) -> str | None:
    folded = _fold(name)
    for category, terms in _CATEGORY_TERMS:
        if any(re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", folded) for term in terms):
            return category
    return None


def _normalize_url(value: str | None) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    try:
        parts = urlsplit(text)
        port = parts.port
    except ValueError:
        return text
    if not parts.scheme or not parts.hostname or parts.username is not None or parts.password is not None:
        return text
    scheme = parts.scheme.lower()
    if scheme not in {"http", "https"}:
        return text
    host = parts.hostname.lower()
    netloc = host if port is None or (scheme, port) in (("http", 80), ("https", 443)) else f"{host}:{port}"
    query = urlencode([(key, item) for key, item in parse_qsl(parts.query, keep_blank_values=True)
                       if not (key.casefold().startswith("utm_") or key.casefold() in {"fbclid", "gclid"})])
    return urlunsplit((scheme, netloc, parts.path or "/", query, ""))


def _normalize_specs(specs: Any) -> Any:
    if not isinstance(specs, Mapping):
        return specs
    normalized = {}
    for key, value in specs.items():
        cleaned_key = _clean_text(key)
        if cleaned_key:
            normalized[cleaned_key] = _normalize_spec_value(value)
    return normalized


def _normalize_spec_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _normalize_specs(value)
    if isinstance(value, list):
        return [_normalize_spec_value(item) for item in value]
    if isinstance(value, tuple):
        return [_normalize_spec_value(item) for item in value]
    return _clean_text(value) if isinstance(value, str) else value


def _normalize_price(value: Decimal | None) -> Decimal | None:
    if not isinstance(value, Decimal) or not value.is_finite():
        return value
    return value.quantize(_CENTS, rounding=ROUND_HALF_UP)


def normalize(raw: RawProduct, category_hint: str | None) -> CatalogProductCandidate:
    """Clean extraction text without inventing missing source facts."""
    name = _clean_text(raw.name)
    category = _category(category_hint) or _category(raw.category) or _keyword_category(name)
    specs = _normalize_specs(raw.specs)
    images = tuple(
        replace(image, original_url=_normalize_url(image.original_url) or image.original_url,
                alt_text=_clean_text(image.alt_text), mime_type=_clean_text(image.mime_type))
        for image in raw.image_candidates
    )
    normalized = replace(
        raw,
        name=name,
        brand=_clean_text(raw.brand),
        category=category,
        price=_normalize_price(raw.price),
        currency=(_clean_text(raw.currency) or "").upper() or None,
        description=_clean_text(raw.description),
        selling_points=tuple(point for value in raw.selling_points if (point := _clean_text(value))),
        specs=specs,
        source_name=_clean_text(raw.source_name),
        source_url=_normalize_url(raw.source_url),
        source_product_id=_clean_text(raw.source_product_id),
        image_candidates=images,
        origin=_clean_text(raw.origin),
        material=_clean_text(raw.material),
        production_date=_clean_text(raw.production_date),
    )
    return CatalogProductCandidate(raw=normalized, stock=10 + CatalogProductCandidate(raw=normalized).seed % 491,
                                   sales=50 + CatalogProductCandidate(raw=normalized).seed % 9951)


def validation_errors(item: CatalogProductCandidate, minimum_time) -> list[str]:
    """Return policy violations; a fresh source update *or* collection is sufficient."""
    raw = item.raw
    errors: list[str] = []
    for field in ("name", "brand", "source_name", "source_url", "source_product_id"):
        if not isinstance(getattr(raw, field), str) or not getattr(raw, field).strip():
            errors.append(f"{field} is required")
    if raw.category not in CATEGORIES:
        errors.append("unsupported category")
    if not isinstance(raw.price, Decimal) or not raw.price.is_finite() or raw.price <= 0:
        errors.append("price must be positive")
    if raw.currency not in _CURRENCIES:
        errors.append(f"unsupported currency: {raw.currency}")
    if not isinstance(raw.specs, Mapping):
        errors.append("specs must be an object")
    else:
        try:
            json.dumps(_normalize_specs(raw.specs), allow_nan=False)
        except (TypeError, ValueError):
            errors.append("specs must be JSON-serializable")
    if not raw.image_candidates:
        errors.append("at least one image is required")
    if not _valid_url(raw.source_url):
        errors.append("source_url must be an absolute HTTP URL")
    if raw.source_updated_at is None or raw.source_updated_at < minimum_time:
        if raw.collected_at < minimum_time:
            errors.append("source is older than minimum_time")
    return errors


def _valid_url(value: str | None) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parts = urlsplit(value)
        parts.port
    except ValueError:
        return False
    return parts.scheme in {"http", "https"} and bool(parts.hostname) and parts.username is None and parts.password is None


def deduplicate(items: list[CatalogProductCandidate]) -> list[CatalogProductCandidate]:
    """Keep the first candidate for each normalized source key and brand/model pair."""
    result: list[CatalogProductCandidate] = []
    source_keys: set[str] = set()
    models: set[tuple[str, str]] = set()
    for item in items:
        source_key = _fold(item.raw.source_name) + "\x1f" + _fold(item.raw.source_product_id)
        model_key = (_fold(item.raw.brand), _fold(item.raw.name))
        if source_key in source_keys or model_key in models:
            continue
        source_keys.add(source_key)
        models.add(model_key)
        result.append(item)
    return result
