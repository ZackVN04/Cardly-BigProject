import pytest

from src.common.enums import DocType
from src.confidence.exceptions import UnsupportedDocumentType
from src.confidence.models import ConfidenceClass, OverallClassification
from src.confidence.service import (
    build_field_scores,
    calculate_overall_score,
    classify_field,
    classify_overall,
)


def _business_card_scores(validation_results=None):
    return build_field_scores(
        document_type=DocType.BUSINESS_CARD,
        normalized_fields={
            "full_name": "Nguyen Van A",
            "position": "Backend Developer",
            "company": "ABC Tech",
            "phone": "0909123456",
            "email": "vana@abc.com",
            "website": "abc.com",
        },
        validation_results=validation_results
        or {
            "email": {"status": "passed", "errors": []},
            "phone": {"status": "passed", "errors": []},
            "website": {"status": "passed", "errors": []},
        },
        field_block_refs={
            "full_name": ["block_001"],
            "position": ["block_002"],
            "company": ["block_003"],
            "email": ["block_004"],
            "phone": ["block_005"],
            "website": ["block_006"],
        },
        ocr_blocks=[
            {"id": "block_001", "text": "Nguyen Van A", "confidence": 0.88},
            {"id": "block_002", "text": "Backend Developer", "confidence": 0.72},
            {"id": "block_003", "text": "ABC Tech", "confidence": 0.92},
            {"id": "block_004", "text": "vana@abc.com", "confidence": 0.98},
            {"id": "block_005", "text": "0909123456", "confidence": 0.95},
            {"id": "block_006", "text": "abc.com", "confidence": 0.94},
        ],
    )


@pytest.mark.asyncio
async def test_high_confidence_auto_approved():
    field_scores = {field.field_name: field for field in _business_card_scores()}

    assert field_scores["email"].classification == ConfidenceClass.HIGH
    assert field_scores["email"].auto_approved is True
    assert field_scores["email"].requires_manual_review is False


@pytest.mark.asyncio
async def test_low_confidence_flagged():
    field_scores = {field.field_name: field for field in _business_card_scores()}

    assert field_scores["company"].classification == ConfidenceClass.LOW
    assert field_scores["company"].auto_approved is False
    assert field_scores["company"].requires_manual_review is True


@pytest.mark.asyncio
async def test_failed_confidence_blocked():
    field_scores = build_field_scores(
        document_type=DocType.BUSINESS_CARD,
        normalized_fields={
            "full_name": "Nguyen Van A",
            "position": "Backend Developer",
            "company": "ABC Tech",
            "phone": "0909123456",
            "email": "vana@abc.com",
            "website": None,
        },
        validation_results={},
        field_block_refs={
            "full_name": ["block_001"],
            "position": ["block_002"],
            "company": ["block_003"],
            "email": ["block_004"],
            "phone": ["block_005"],
        },
        ocr_blocks=[
            {"id": "block_001", "text": "Nguyen Van A", "confidence": 0.88},
            {"id": "block_002", "text": "Backend Developer", "confidence": 0.72},
            {"id": "block_003", "text": "ABC Tech", "confidence": 0.92},
            {"id": "block_004", "text": "vana@abc.com", "confidence": 0.98},
            {"id": "block_005", "text": "0909123456", "confidence": 0.95},
        ],
    )
    field_scores = {field.field_name: field for field in field_scores}

    assert field_scores["website"].value is None
    assert field_scores["website"].score == 0.0
    assert field_scores["website"].classification == ConfidenceClass.FAILED
    assert field_scores["website"].requires_manual_review is True


def test_business_card_only_scores_six_fixed_fields():
    field_names = [field.field_name for field in _business_card_scores()]

    assert field_names == [
        "full_name",
        "position",
        "company",
        "phone",
        "email",
        "website",
    ]


def test_business_card_overall_uses_required_groups():
    field_scores = _business_card_scores()

    overall_score = calculate_overall_score(DocType.BUSINESS_CARD, field_scores)

    assert overall_score == 0.95
    assert classify_overall(overall_score) == OverallClassification.SUCCESS


def test_validation_failure_blocks_auto_approval():
    field_scores = {
        field.field_name: field
        for field in _business_card_scores(
            validation_results={
                "email": {
                    "status": "failed",
                    "errors": ["Invalid email format"],
                },
            }
        )
    }

    assert field_scores["email"].score == 0.98
    assert field_scores["email"].classification == ConfidenceClass.HIGH
    assert field_scores["email"].validation_status == "failed"
    assert field_scores["email"].auto_approved is False
    assert field_scores["email"].requires_manual_review is True


def test_classify_field_thresholds():
    assert classify_field(0.95) == ConfidenceClass.HIGH
    assert classify_field(0.70) == ConfidenceClass.LOW
    assert classify_field(0.69) == ConfidenceClass.FAILED


def test_rejects_non_business_card_document_type():
    with pytest.raises(UnsupportedDocumentType):
        build_field_scores(
            document_type=DocType.PASSPORT_AU,
            normalized_fields={},
            validation_results={},
            field_block_refs={},
            ocr_blocks=[],
        )
