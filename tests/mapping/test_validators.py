import pytest

from src.mapping.validators import (
    is_iso_date,
    luhn_medicare,
    not_in_past,
    regex_passport_au,
)


@pytest.mark.parametrize("value, expected", [
    ("BN8038374", True),
    ("A1234567", True),
    ("12345678", False),   # no letters
    ("ABCD1234567", False),  # too many letters
    (None, False),
])
def test_regex_passport_au(value, expected):
    assert regex_passport_au(value) == expected


@pytest.mark.parametrize("value, expected", [
    ("2134567890", True),
    ("1234 56789 1", True),
    ("123", False),
    (None, False),
])
def test_luhn_medicare(value, expected):
    assert luhn_medicare(value) == expected


def test_not_in_past_future_date():
    assert not_in_past("2099-01-01") is True


def test_not_in_past_old_date():
    assert not_in_past("2000-01-01") is False


def test_is_iso_date_valid():
    assert is_iso_date("2024-10-01") is True


def test_is_iso_date_invalid():
    assert is_iso_date("01-10-2024") is False
