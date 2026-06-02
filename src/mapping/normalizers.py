import re
from typing import Any

from src.common.enums import DocType


NULL_LIKE_VALUES = {"", "null", "none", "n/a", "na", "not available"}


def normalize_null_like(value: str | None) -> str | None:
    """Convert empty and placeholder strings returned by OCR/LLM to None."""
    if value is None:
        return None
    stripped = value.strip()
    return None if stripped.lower() in NULL_LIKE_VALUES else stripped


def normalize_phone(value: str | None) -> str | None:
    """Standardize phone format: remove spaces/formatting, convert 0... to +84..."""
    value = normalize_null_like(value)
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
    value = normalize_null_like(value)
    if value is None:
        return None
    return value.lower()


def normalize_web(value: str | None) -> str | None:
    """Ensure web/URL starts with https:// if protocol is missing."""
    value = normalize_null_like(value)
    if value is None:
        return None
    cleaned = value
    if not re.match(r"^https?://", cleaned, re.IGNORECASE):
        cleaned = "https://" + cleaned
    return cleaned


def clean_text(value: str | None) -> str | None:
    """Strip leading/trailing whitespace and collapse internal spaces."""
    value = normalize_null_like(value)
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
        elif key == "phones" and isinstance(v, list):
            v = [
                normalized_phone
                for item in v
                if isinstance(item, str)
                for normalized_phone in [normalize_phone(item)]
                if normalized_phone
            ]
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
