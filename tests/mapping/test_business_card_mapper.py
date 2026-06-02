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


def test_extract_from_raw_text_when_vision_regions_share_same_bbox():
    raw_text = "\n".join([
        "Institute for ComputerSciences,Social Informatics",
        "and Telecommunications Engineering",
        "ICST.ORG",
        "Gabriella MAGYAR",
        "Conference Coordinator",
        "Begijnhoflaan 93a,B-9000Gent,Belgium",
        "phone:+3293299425",
        "e-mail:gabriella.magyar@icst.org",
        "skype:gabriella.magyar-icst",
        "GentBostonHong KongSydneyAlexandria",
        "WWw",
    ])
    ocr_result = {
        "raw_text": raw_text,
        "blocks": [
            {"text": line, "bbox": [0, 0, 10, 10], "confidence": 0.95}
            for line in raw_text.splitlines()
        ],
    }
    vision_result = {
        "detected_regions": [
            {"label": field, "bbox": [0, 0, 10, 10], "confidence": 0.95}
            for field in ["name", "phone", "email", "web", "position", "company"]
        ]
    }

    mapper = BusinessCardMapper(ocr_result=ocr_result, vision_result=vision_result)
    result = mapper.extract()

    assert result["name"] == "Gabriella MAGYAR"
    assert result["phone"] == "+3293299425"
    assert result["email"] == "gabriella.magyar@icst.org"
    assert result["web"] == "ICST.ORG"
    assert result["position"] == "Conference Coordinator"
    assert result["company"] == (
        "Institute for ComputerSciences,Social Informatics "
        "and Telecommunications Engineering"
    )


def test_extract_uppercase_name_before_company_without_website():
    raw_text = "\n".join([
        "NGUYEN THI NGOC DIEP",
        "SWINBURNE VIETNAM",
        "Director",
        "ALLIANCE PROGRAM",
        "600 Nguyen Van Cu Street",
        "An Binh Ward,Can Tho,Vietnam.",
        "SWIN",
        "SWINBURNE",
        "BUR",
        "UNIVERSITY OF",
        "Contact",
        "TECHNOLOGY",
        "NE",
        "+84)903334966",
        "DiepNTN12@fe.edu.vn",
        "Alliance with",
        "Education",
    ])
    ocr_result = {
        "raw_text": raw_text,
        "blocks": [
            {"text": line, "bbox": [0, 0, 10, 10], "confidence": 0.95}
            for line in raw_text.splitlines()
        ],
    }
    vision_result = {
        "detected_regions": [
            {"label": field, "bbox": [0, 0, 10, 10], "confidence": 0.95}
            for field in ["name", "phone", "email", "web", "position", "company"]
        ]
    }

    mapper = BusinessCardMapper(ocr_result=ocr_result, vision_result=vision_result)
    result = mapper.extract()

    assert result["name"] == "NGUYEN THI NGOC DIEP"
    assert result["phone"] == "+84)903334966"
    assert result["email"] == "DiepNTN12@fe.edu.vn"
    assert result["web"] is None
    assert result["position"] == "Director"
    assert result["company"] == "SWINBURNE VIETNAM"
