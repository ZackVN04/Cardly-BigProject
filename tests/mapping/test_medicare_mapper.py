"""Tests for MedicareMapper using mock_data/medicare_ocr_output.json"""
import json
from pathlib import Path

import pytest

from src.mapping.mappers.medicare import MedicareMapper


@pytest.fixture
def medicare_ocr() -> dict:
    path = Path(__file__).parents[2] / "mock_data" / "medicare_ocr_output.json"
    return json.loads(path.read_text())


def test_extract_all_keys_present(medicare_ocr):
    mapper = MedicareMapper(
        ocr_result=medicare_ocr["ocr"],
        vision_result=medicare_ocr["vision"],
    )
    result = mapper.extract()
    for key in ["card_number", "irn", "full_name", "valid_to"]:
        assert key in result
