import re
from typing import Any

from src.common.enums import DocType


def normalize_phone(value: str | None) -> str | None:
    """Standardize phone format: remove spaces/formatting, convert 0... to +84..."""
    if value is None:
        return None
    # Keep only digits and '+'
    cleaned = re.sub(r"[^\d+]", "", value.strip())
    # Convert local Vietnamese format (e.g. 0912345678) to international (+84912345678)
    if cleaned.startswith("0") and len(cleaned) == 10:
        cleaned = "+84" + cleaned[1:]
    return cleaned


def normalize_email(value: str | None) -> str | None:
    """Trim and lowercase email addresses."""
    if value is None:
        return None
    return value.strip().lower()


def normalize_web(value: str | None) -> str | None:
    """Ensure web/URL starts with https:// if protocol is missing."""
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return cleaned
    if not re.match(r"^https?://", cleaned, re.IGNORECASE):
        cleaned = "https://" + cleaned
    return cleaned


def clean_text(value: str | None) -> str | None:
    """Strip leading/trailing whitespace and collapse internal spaces."""
    if value is None:
        return None
    return " ".join(value.split())


def normalize_fields(doc_type: DocType, extracted: dict[str, Any]) -> dict[str, Any]:
    """Apply all normalizations appropriate for the given doc_type."""
    normalized: dict[str, Any] = {}

    for key, value in extracted.items():
        v = value
        if key == "phone" and isinstance(v, str):
            v = normalize_phone(v)
        elif key == "email" and isinstance(v, str):
            v = normalize_email(v)
        elif (key == "web" or key == "website") and isinstance(v, str):
            v = normalize_web(v)
        elif isinstance(v, str):
            v = clean_text(v)
        elif isinstance(v, list):
            # E.g. keywords, highlights
            v = [clean_text(item) for item in v if isinstance(item, str)]
        normalized[key] = v

    return normalized
