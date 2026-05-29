import pytest

from src.common.enums import DocType
from src.mapping.validators import (
    validate_email_format,
    validate_phone_format,
    validate_url_format,
    validate_fields,
)


@pytest.mark.parametrize("value, expected", [
    ("test@domain.com", True),
    ("user.name+tag@sub.domain.co.uk", True),
    ("invalid-email", False),
    ("email@domain", False),
    (None, False),
])
def test_validate_email_format(value, expected):
    assert validate_email_format(value) == expected


@pytest.mark.parametrize("value, expected", [
    ("+84912345678", True),
    ("0912345678", True),
    ("+15550199", True),
    ("+3293299425", True),
    ("+61298765432", True),
    ("123", False),       # too short
    ("12345678901234567", False),  # too long
    ("phone123", False),  # letters
    (None, False),
])
def test_validate_phone_format(value, expected):
    assert validate_phone_format(value) == expected


@pytest.mark.parametrize("value, expected", [
    ("https://www.company.com", True),
    ("http://example.com/page?query=1", True),
    ("www.example.com", False),  # protocol missing
    ("invalid-url", False),
    (None, False),
])
def test_validate_url_format(value, expected):
    assert validate_url_format(value) == expected


def test_validate_fields_business_card():
    # Valid and complete
    normalized = {
        "name": "Nguyễn Văn A",
        "phone": "+84912345678",
        "email": "nguyen.vana@company.com",
        "web": "https://www.company.com",
    }
    results, missing = validate_fields(DocType.BUSINESS_CARD, normalized)

    assert missing == []
    assert len(results) == 3
    assert all(r.passed for r in results)

    # Missing email (required) and invalid phone format
    normalized_invalid = {
        "name": "Nguyễn Văn A",
        "phone": "invalid-phone",
        "web": "https://www.company.com",
    }
    results, missing = validate_fields(DocType.BUSINESS_CARD, normalized_invalid)

    assert missing == ["email"]
    # email validation rule doesn't run since it's not present
    # phone rule runs but fails
    assert len(results) == 2  # phone, web
    phone_res = next(r for r in results if r.field_name == "phone")
    assert phone_res.passed is False
