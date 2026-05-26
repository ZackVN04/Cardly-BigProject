import pytest

from src.common.enums import DocType
from src.mapping.normalizers import (
    clean_text,
    normalize_phone,
    normalize_email,
    normalize_web,
    normalize_fields,
)


@pytest.mark.parametrize("raw, expected", [
    ("+84 912 345 678", "+84912345678"),
    ("0912 345 678", "+84912345678"),
    ("0909-123-456", "+84909123456"),
    ("+1 555-0199", "+15550199"),
    (None, None),
])
def test_normalize_phone(raw, expected):
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize("raw, expected", [
    ("  TEST@DOMAIN.COM  ", "test@domain.com"),
    ("john.doe@company.co.uk", "john.doe@company.co.uk"),
    (None, None),
])
def test_normalize_email(raw, expected):
    assert normalize_email(raw) == expected


@pytest.mark.parametrize("raw, expected", [
    ("www.company.com", "https://www.company.com"),
    ("http://example.com", "http://example.com"),
    ("https://my-site.vn/home", "https://my-site.vn/home"),
    (None, None),
])
def test_normalize_web(raw, expected):
    assert normalize_web(raw) == expected


def test_clean_text():
    assert clean_text("  hello   world  ") == "hello world"
    assert clean_text(None) is None


def test_normalize_fields_business_card():
    extracted = {
        "name": " Nguyễn Văn A ",
        "phone": " 0912 345 678 ",
        "email": " Nguyễn.Văn.A@Company.Com ",
        "web": " www.company.com ",
        "position": " Kỹ sư phần mềm ",
        "company": " TECH SOLUTIONS JSC ",
        "keywords": ["  tag1 ", " tag2  "]
    }
    normalized = normalize_fields(DocType.BUSINESS_CARD, extracted)

    assert normalized["name"] == "Nguyễn Văn A"
    assert normalized["phone"] == "+84912345678"
    assert normalized["email"] == "nguyễn.văn.a@company.com"
    assert normalized["web"] == "https://www.company.com"
    assert normalized["position"] == "Kỹ sư phần mềm"
    assert normalized["company"] == "TECH SOLUTIONS JSC"
    assert normalized["keywords"] == ["tag1", "tag2"]
