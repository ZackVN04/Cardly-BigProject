import re
from typing import Any

from src.common.enums import DocType
from src.mapping.constants import REQUIRED_FIELDS
from src.mapping.models import FieldValidationResult


def validate_email_format(value: str | None) -> bool:
    """Validate email format using a standard regex."""
    if not value:
        return False
    email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(email_regex, value.strip()))


def validate_phone_format(value: str | None) -> bool:
    """Validate phone format: optionally starts with +, followed by 7-15 digits."""
    if not value:
        return False
    # Keep only digits and '+' to evaluate clean phone length
    cleaned = re.sub(r"[^\d+]", "", value.strip())
    phone_regex = r"^\+?\d{7,15}$"
    return bool(re.match(phone_regex, cleaned))


def validate_url_format(value: str | None) -> bool:
    """Validate website/URL format."""
    if not value:
        return False
    # URL should start with http:// or https:// (normally added by normalizer)
    url_regex = r"^https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(/.*)?$"
    return bool(re.match(url_regex, value.strip(), re.IGNORECASE))


RULES: dict[str, list[tuple[str, Any]]] = {
    DocType.BUSINESS_CARD: [
        ("email", [("email_format", validate_email_format)]),
        ("phone", [("phone_format", validate_phone_format)]),
        ("web",   [("url_format",   validate_url_format)]),
    ],
}


def validate_fields(
    doc_type: DocType,
    normalized: dict[str, Any],
) -> tuple[list[FieldValidationResult], list[str]]:
    """Run all validation rules for the given doc_type.
    Returns (validation_results, missing_required_fields).
    """
    results: list[FieldValidationResult] = []
    required = REQUIRED_FIELDS.get(doc_type, [])
    missing: list[str] = [f for f in required if not normalized.get(f)]

    for field_name, rules in RULES.get(doc_type, []):
        val = normalized.get(field_name)
        # Only run format validation rules if the field is present/non-empty
        if val not in (None, ""):
            for rule_name, rule_fn in rules:
                passed = rule_fn(val)
                results.append(FieldValidationResult(
                    field_name=field_name,
                    rule=rule_name,
                    passed=passed,
                ))

    return results, missing
