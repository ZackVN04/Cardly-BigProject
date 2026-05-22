"""Tests for PassportMapper using mock_data/passport_au_ocr_output.json"""
import json
from pathlib import Path

import pytest

from src.mapping.mappers.passport_au import PassportMapper


@pytest.fixture
def passport_ocr() -> dict:
    path = Path(__file__).parents[2] / "mock_data" / "passport_au_ocr_output.json"
    return json.loads(path.read_text())


def test_extract_all_keys_present(passport_ocr):
    mapper = PassportMapper(
        ocr_result=passport_ocr["ocr"],
        vision_result=passport_ocr["vision"],
    )
    result = mapper.extract()
    expected_keys = [
        "document_no", "type", "country_code", "surname", "given_names",
        "nationality", "date_of_birth", "sex", "place_of_birth",
        "date_of_issue", "date_of_expiry", "authority", "mrz_line1", "mrz_line2",
    ]
    for key in expected_keys:
        assert key in result, f"Missing key: {key}"


def test_extract_no_dropped_keys(passport_ocr):
    """Fields not extractable must be None, not missing."""
    mapper = PassportMapper(
        ocr_result={"blocks": [], "raw_text": ""},
        vision_result={"doc_type": "passport_au", "detected_regions": []},
    )
    result = mapper.extract()
    for key in mapper.FIELD_LABELS:
        assert key in result
        assert result[key] is None
