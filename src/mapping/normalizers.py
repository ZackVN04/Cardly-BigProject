# TODO(P5 — Hui): Implement normalizers
import re
import unicodedata
from typing import Any

from src.common.enums import DocType


COUNTRY_CODES: dict[str, str] = {
    "AUSTRALIAN": "AUS",
    "AUSTRALIA": "AUS",
}

DATE_PATTERNS = [
    (r"(\d{2})\s+(\w{3})\s+(\d{4})", "%d %b %Y"),   # 03 MAY 2000
    (r"(\d{2})/(\d{2})/(\d{4})", "%d/%m/%Y"),         # 03/05/2000
    (r"(\d{4})-(\d{2})-(\d{2})", "%Y-%m-%d"),          # 2000-05-03 (already ISO)
]


def normalize_date(value: str | None) -> str | None:
    """Convert various date strings to ISO-8601 (YYYY-MM-DD)."""
    if value is None:
        return None
    from datetime import datetime
    value = value.strip()
    for pattern, fmt in DATE_PATTERNS:
        if re.fullmatch(pattern, value, re.IGNORECASE):
            try:
                return datetime.strptime(value.upper(), fmt.upper()).strftime("%Y-%m-%d")
            except ValueError:
                continue
    return value


def normalize_country_code(value: str | None) -> str | None:
    """Map full country names to ISO 3166-1 alpha-3 codes."""
    if value is None:
        return None
    return COUNTRY_CODES.get(value.strip().upper(), value.strip().upper())


def clean_text(value: str | None) -> str | None:
    """Strip leading/trailing whitespace and collapse internal spaces."""
    if value is None:
        return None
    return " ".join(value.split())


def strip_diacritics(value: str | None) -> str | None:
    """Remove diacritics from a string (e.g. Pérez → Perez)."""
    if value is None:
        return None
    return "".join(
        c for c in unicodedata.normalize("NFD", value)
        if unicodedata.category(c) != "Mn"
    )


def normalize_fields(doc_type: DocType, extracted: dict[str, Any]) -> dict[str, Any]:
    """Apply all normalizations appropriate for the given doc_type."""
    normalized: dict[str, Any] = {}

    date_fields = {
        DocType.PASSPORT_AU: ["date_of_birth", "date_of_issue", "date_of_expiry"],
        DocType.MEDICARE: [],
        DocType.DRIVER_LICENCE_VIC: ["date_of_birth", "licence_expiry"],
    }.get(doc_type, [])

    country_fields = {
        DocType.PASSPORT_AU: ["nationality", "country_code"],
    }.get(doc_type, [])

    for key, value in extracted.items():
        v = value
        if key in date_fields:
            v = normalize_date(v) if isinstance(v, str) else v
        elif key in country_fields:
            v = normalize_country_code(v) if isinstance(v, str) else v
        elif isinstance(v, str):
            v = clean_text(v)
        normalized[key] = v

    return normalized
