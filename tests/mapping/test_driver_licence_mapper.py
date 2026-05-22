"""Tests for DriverLicenceMapper using mock_data/driver_licence_vic_ocr_output.json"""
import json
from pathlib import Path

import pytest

from src.mapping.mappers.driver_licence_vic import DriverLicenceMapper


@pytest.fixture
def dl_ocr() -> dict:
    path = Path(__file__).parents[2] / "mock_data" / "driver_licence_vic_ocr_output.json"
    return json.loads(path.read_text())


def test_extract_all_keys_present(dl_ocr):
    mapper = DriverLicenceMapper(
        ocr_result=dl_ocr["ocr"],
        vision_result=dl_ocr["vision"],
    )
    result = mapper.extract()
    for key in ["licence_no", "full_name", "address", "date_of_birth",
                "licence_expiry", "licence_type", "conditions", "state"]:
        assert key in result


def test_state_defaults_to_vic():
    mapper = DriverLicenceMapper(
        ocr_result={"blocks": [], "raw_text": ""},
        vision_result={"doc_type": "driver_licence_vic", "detected_regions": []},
    )
    result = mapper.extract()
    assert result["state"] == "VIC"
