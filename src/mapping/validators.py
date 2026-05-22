# TODO(P5 — Hui): Implement validators
import re
from datetime import date
from typing import Any

from src.common.enums import DocType
from src.mapping.models import FieldValidationResult
from src.mapping.constants import REQUIRED_FIELDS


def regex_passport_au(value: str | None) -> bool:
    """Australian passport number: 1-2 letters + 7 digits."""
    if value is None:
        return False
    return bool(re.fullmatch(r"[A-Z]{1,2}\d{7}", value.strip().upper()))


def mrz_checksum(mrz_line: str | None) -> bool:
    """Validate MRZ check digit using ICAO 9303 algorithm."""
    if not mrz_line:
        return False
    weights = [7, 3, 1]
    total = 0
    for i, ch in enumerate(mrz_line[:-1]):
        if ch.isdigit():
            val = int(ch)
        elif ch.isalpha():
            val = ord(ch.upper()) - 55
        elif ch == "<":
            val = 0
        else:
            return False
        total += val * weights[i % 3]
    return total % 10 == int(mrz_line[-1])


def luhn_medicare(card_number: str | None) -> bool:
    """Basic Medicare card number validation (10 digits)."""
    if not card_number:
        return False
    digits = re.sub(r"\s", "", card_number)
    return bool(re.fullmatch(r"\d{10}", digits))


def not_in_past(value: str | None) -> bool:
    """Return True if ISO date string is today or in the future."""
    if not value:
        return False
    try:
        return date.fromisoformat(value) >= date.today()
    except ValueError:
        return False


def is_iso_date(value: str | None) -> bool:
    """Return True if value is a valid ISO-8601 date (YYYY-MM-DD)."""
    if not value:
        return False
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


RULES: dict[str, list[tuple[str, Any]]] = {
    DocType.PASSPORT_AU: [
        ("document_no",    [("regex_passport_au", regex_passport_au)]),
        ("date_of_expiry", [("not_in_past", not_in_past), ("is_iso_date", is_iso_date)]),
        ("date_of_birth",  [("is_iso_date", is_iso_date)]),
    ],
    DocType.MEDICARE: [
        ("card_number",    [("luhn_medicare", luhn_medicare)]),
    ],
    DocType.DRIVER_LICENCE_VIC: [
        ("date_of_expiry", [("not_in_past", not_in_past)]),
        ("date_of_birth",  [("is_iso_date", is_iso_date)]),
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
        for rule_name, rule_fn in rules:
            passed = rule_fn(normalized.get(field_name))
            results.append(FieldValidationResult(
                field_name=field_name,
                rule=rule_name,
                passed=passed,
            ))

    return results, missing
