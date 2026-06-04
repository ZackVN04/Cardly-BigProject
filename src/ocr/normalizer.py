from __future__ import annotations

from typing import Any

from .response_schema import ExtractionResponse


def normalize_gemini_response(
    gemini_raw: dict[str, Any],
    ocr_blocks: list[dict[str, Any]],
    raw_text: str,
) -> ExtractionResponse:
    """Normalize Gemini JSON into the stable OCR API response shape."""
    phones = _as_list(gemini_raw.get("phones") or gemini_raw.get("phone"))
    social_profiles = _as_list(gemini_raw.get("social_profiles"))

    values: dict[str, Any] = {
        "name": _as_optional_str(gemini_raw.get("name")),
        "phones": phones,
        "email": _as_optional_str(gemini_raw.get("email")),
        "company": _as_optional_str(gemini_raw.get("company")),
        "position": _as_optional_str(gemini_raw.get("position")),
        "address": _as_optional_str(gemini_raw.get("address")),
        "website": _as_optional_str(gemini_raw.get("website") or gemini_raw.get("web")),
        "social_profiles": social_profiles,
    }

    return ExtractionResponse(
        **values,
        field_confidences=_field_confidences(values, ocr_blocks),
        raw_text=raw_text,
        extraction_status="completed",
    )


def _as_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"null", "none", "n/a"}:
        return None
    return text


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [text for item in value if (text := _as_optional_str(item))]
    text = _as_optional_str(value)
    return [text] if text else []


def _field_confidences(
    values: dict[str, Any],
    ocr_blocks: list[dict[str, Any]],
) -> dict[str, float]:
    confidences: dict[str, float] = {}
    for field, value in values.items():
        candidates = value if isinstance(value, list) else [value]
        best = 0.0
        for candidate in candidates:
            if not isinstance(candidate, str) or not candidate.strip():
                continue
            needle = candidate.strip().lower()
            for block in ocr_blocks:
                text = str(block.get("text", "")).lower()
                if needle in text or text in needle:
                    best = max(best, float(block.get("confidence", 0.0)))
        if best:
            confidences[field] = best
    return confidences
