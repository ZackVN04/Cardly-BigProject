import pytest

from src.mapping.normalizers import (
    clean_text,
    normalize_country_code,
    normalize_date,
    strip_diacritics,
)


@pytest.mark.parametrize("raw, expected", [
    ("03 MAY 2000", "2000-05-03"),
    ("01/10/2024", "2024-10-01"),
    ("2034-10-01", "2034-10-01"),
    (None, None),
])
def test_normalize_date(raw, expected):
    assert normalize_date(raw) == expected


@pytest.mark.parametrize("raw, expected", [
    ("AUSTRALIAN", "AUS"),
    ("Australia", "AUS"),
    ("USA", "USA"),
    (None, None),
])
def test_normalize_country_code(raw, expected):
    assert normalize_country_code(raw) == expected


def test_clean_text_strips_whitespace():
    assert clean_text("  hello   world  ") == "hello world"


def test_strip_diacritics():
    assert strip_diacritics("Pérez") == "Perez"
