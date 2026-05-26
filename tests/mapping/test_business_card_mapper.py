import json
from pathlib import Path

import pytest

from src.mapping.mappers.business_card import BusinessCardMapper


@pytest.fixture
def business_card_ocr() -> dict:
    path = Path(__file__).parents[2] / "mock_data" / "business_card_ocr_output.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_extract_business_card_fields(business_card_ocr):
    mapper = BusinessCardMapper(
        ocr_result=business_card_ocr["ocr"],
        vision_result=business_card_ocr["vision"],
    )
    result = mapper.extract()

    assert result["name"] == "Nguyễn Văn A"
    assert result["phone"] == "+84 912 345 678"
    assert result["email"] == "nguyen.vana@company.com"
    assert result["web"] == "www.company.com"
    assert result["position"] == "Kỹ sư phần mềm"
    assert result["company"] == "TECH SOLUTIONS JSC"


def test_extract_fallback_heuristics_when_vision_regions_missing():
    # vision result is empty but ocr has the text blocks
    ocr_result = {
        "blocks": [
            {"text": "Random Company Name Ltd", "bbox": [10, 10, 100, 20], "confidence": 0.9},
            {"text": "John Doe", "bbox": [10, 40, 100, 20], "confidence": 0.9},
            {"text": "Mobile: +84999999999", "bbox": [10, 70, 100, 20], "confidence": 0.9},
            {"text": "Email: john.doe@example.com", "bbox": [10, 100, 100, 20], "confidence": 0.9},
            {"text": "Web: www.example.com", "bbox": [10, 130, 100, 20], "confidence": 0.9},
        ]
    }
    vision_result = {"detected_regions": []}

    mapper = BusinessCardMapper(ocr_result=ocr_result, vision_result=vision_result)
    result = mapper.extract()

    # fallbacks should locate phone, email, and web from blocks
    assert result["email"] == "john.doe@example.com"
    assert result["phone"] == "+84999999999"
    assert result["web"] == "www.example.com"
