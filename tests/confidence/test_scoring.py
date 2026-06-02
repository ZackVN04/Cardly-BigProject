import pytest

from src.common.enums import DocType
from src.confidence import service as confidence_service
from src.confidence.exceptions import UnsupportedDocumentType
from src.confidence.models import ConfidenceClass, OverallClassification
from src.confidence.service import (
    _scan_field_scores,
    build_field_scores,
    calculate_overall_score,
    classify_field,
    classify_overall,
)

pytestmark = pytest.mark.no_db


def _business_card_scores(validation_results=None):
    return build_field_scores(
        document_type=DocType.BUSINESS_CARD,
        normalized_fields={
            "name": "Nguyen Van A",
            "position": "Backend Developer",
            "company": "ABC Tech",
            "phones": ["+32 9 329 94 25"],
            "email": "vana@abc.com",
            "website": "https://abc.com",
            "address": "123 Main Street",
        },
        validation_results=validation_results
        or {
            "email": {"status": "passed", "errors": []},
            "phones": {"status": "passed", "errors": []},
            "website": {"status": "passed", "errors": []},
        },
        field_block_refs={
            "name": ["block_001"],
            "position": ["block_002"],
            "company": ["block_003"],
            "email": ["block_004"],
            "phones": ["block_005"],
            "website": ["block_006"],
            "address": ["block_007"],
        },
        ocr_blocks=[
            {"id": "block_001", "text": "Nguyen Van A", "confidence": 0.88},
            {"id": "block_002", "text": "Backend Developer", "confidence": 0.72},
            {"id": "block_003", "text": "ABC Tech", "confidence": 0.92},
            {"id": "block_004", "text": "vana@abc.com", "confidence": 0.98},
            {"id": "block_005", "text": "+32 9 329 94 25", "confidence": 0.95},
            {"id": "block_006", "text": "abc.com", "confidence": 0.94},
            {"id": "block_007", "text": "123 Main Street", "confidence": 0.90},
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
            "name": "Nguyen Van A",
            "position": "Backend Developer",
            "company": "ABC Tech",
            "phones": ["+3293299425"],
            "email": "vana@abc.com",
            "website": None,
            "address": "123 Main Street",
        },
        validation_results={},
        field_block_refs={
            "name": ["block_001"],
            "position": ["block_002"],
            "company": ["block_003"],
            "email": ["block_004"],
            "phones": ["block_005"],
            "address": ["block_007"],
        },
        ocr_blocks=[
            {"id": "block_001", "text": "Nguyen Van A", "confidence": 0.88},
            {"id": "block_002", "text": "Backend Developer", "confidence": 0.72},
            {"id": "block_003", "text": "ABC Tech", "confidence": 0.92},
            {"id": "block_004", "text": "vana@abc.com", "confidence": 0.98},
            {"id": "block_005", "text": "+32 9 329 94 25", "confidence": 0.95},
            {"id": "block_007", "text": "123 Main Street", "confidence": 0.90},
        ],
    )
    field_scores = {field.field_name: field for field in field_scores}

    assert field_scores["website"].value is None
    assert field_scores["website"].score == 0.0
    assert field_scores["website"].classification == ConfidenceClass.FAILED
    assert field_scores["website"].requires_manual_review is True


def test_business_card_scores_seven_fixed_fields():
    field_names = [field.field_name for field in _business_card_scores()]

    assert field_names == [
        "name",
        "phones",
        "email",
        "company",
        "position",
        "address",
        "website",
    ]


def test_business_card_overall_uses_required_groups():
    field_scores = _business_card_scores()

    overall_score = calculate_overall_score(DocType.BUSINESS_CARD, field_scores)

    assert overall_score == 0.8986
    assert classify_overall(overall_score) == OverallClassification.PARTIAL_SUCCESS


def test_compact_text_matching_scores_normalized_phone_and_url():
    field_scores = build_field_scores(
        document_type=DocType.BUSINESS_CARD,
        normalized_fields={
            "name": "NGUYEN THI NGOC DIEP",
            "position": "Director",
            "company": "SWINBURNE VIETNAM",
            "phone": "+84903334966",
            "email": "diepntn12@fe.edu.vn",
            "web": "https://ICST.ORG",
        },
        validation_results={},
        ocr_blocks=[
            {"id": "block_001", "text": "NGUYEN THI NGOC DIEP", "confidence": 0.95},
            {"id": "block_002", "text": "Director", "confidence": 0.95},
            {"id": "block_003", "text": "SWINBURNE VIETNAM", "confidence": 0.95},
            {"id": "block_004", "text": "+84)903334966", "confidence": 0.95},
            {"id": "block_005", "text": "DiepNTN12@fe.edu.vn", "confidence": 0.95},
            {"id": "block_006", "text": "ICST.ORG", "confidence": 0.95},
        ],
    )
    by_name = {field.field_name: field for field in field_scores}

    assert by_name["phones"].score == 0.95
    assert by_name["website"].score == 0.95


def test_international_phone_scores_after_normalization():
    field_scores = build_field_scores(
        document_type=DocType.BUSINESS_CARD,
        normalized_fields={
            "name": "Gabriella Magyar",
            "position": "Conference Coordinator",
            "company": "ICST",
            "phone": "+3293299425",
            "email": "gabriella.magyar@icst.org",
            "web": None,
        },
        validation_results={},
        ocr_blocks=[
            {"id": "block_001", "text": "Gabriella Magyar", "confidence": 0.95},
            {"id": "block_002", "text": "Conference Coordinator", "confidence": 0.95},
            {"id": "block_003", "text": "ICST", "confidence": 0.95},
            {"id": "block_004", "text": "phone:+32 9 329 94 25", "confidence": 0.95},
            {"id": "block_005", "text": "gabriella.magyar@icst.org", "confidence": 0.95},
        ],
    )
    by_name = {field.field_name: field for field in field_scores}

    assert by_name["phones"].score == 0.95
    assert by_name["phones"].classification == ConfidenceClass.HIGH


def test_international_phone_scores_after_normalization_without_block_refs():
    field_scores = build_field_scores(
        document_type=DocType.BUSINESS_CARD,
        normalized_fields={
            "name": "Jane Doe",
            "position": "Director",
            "company": "Example Pty Ltd",
            "phones": ["+61298765432"],
            "email": "jane@example.com",
            "website": "https://example.com",
            "address": "Sydney, Australia",
        },
        validation_results={},
        ocr_blocks=[
            {"text": "+61 (2) 9876 5432", "confidence": 0.97},
        ],
    )
    by_name = {field.field_name: field for field in field_scores}

    assert by_name["phones"].score == 0.97
    assert by_name["phones"].classification == ConfidenceClass.HIGH


def test_scan_fallback_rejects_truncated_name_score():
    field_scores = _scan_field_scores(
        normalized_fields={
            "name": "Margie",
            "phones": ["6035550160", "6035550178"],
            "email": None,
            "company": "Margie's Travel",
            "position": "Manager",
            "address": "8172 Miramar Road, San Diego, CA 12793",
            "website": "https://www.margiestravel.com",
        },
        validation_results={},
        stored_scores=[
            {"field_name": "name", "score": 0.989},
            {"field_name": "phones", "score": 0.9845},
            {"field_name": "company", "score": 0.9728},
            {"field_name": "position", "score": 0.9975},
            {"field_name": "address", "score": 0.9537},
            {"field_name": "website", "score": 0.9968},
        ],
        raw_text=(
            "8172 Miramar Road\n"
            "MARGIESHOOP\n"
            "San Diego,CA 12793\n"
            "Manager\n"
            "Ph.603-555-0160\n"
            "Fax 603-555-0161\n"
            "Cell 603-555-0178\n"
            "Margie's Travel\n"
            "www.margiestravel.com"
        ),
    )
    by_name = {field.field_name: field for field in field_scores}

    assert by_name["name"].score == 0.0
    assert by_name["name"].classification == ConfidenceClass.FAILED
    assert by_name["phones"].score == 0.9845
    assert by_name["website"].score == 0.9968


def test_scan_fallback_accepts_company_and_position_from_combined_ocr_line():
    field_scores = _scan_field_scores(
        normalized_fields={
            "name": "Le Thi Lam Tuyen",
            "phones": ["+84888494588"],
            "email": "tuyenltl2@fe.edu.vn",
            "company": "FPT University Can Tho Campus",
            "position": "Head of Corporate Relations Department",
            "address": "600 Nguyen Van Cu St. An Binh Ward, Ninh Kieu Dist. Cantho",
            "website": "https://cantho.fpt.edu.vn",
        },
        validation_results={},
        stored_scores=[
            {"field_name": "company", "score": 0.0},
            {"field_name": "position", "score": 0.9668},
        ],
        raw_text=(
            "Le Thi Lam Tuyen (Ms)\n"
            "Head of Corporate Relations Department-FPT Univeristy Can Tho Campus\n"
            "+84)888494588\n"
            "Tuyenltl2@fe.edu.vn\n"
            "600 Nguyen Van Cu St.An Binh Ward, Ninh Kieu Dist.Cantho\n"
            "cantho.fpt.edu.vn"
        ),
    )
    by_name = {field.field_name: field for field in field_scores}

    assert by_name["company"].score == 0.9668
    assert by_name["position"].score == 0.9668


def test_ocr_scoring_accepts_company_with_typo_inside_combined_line():
    field_scores = build_field_scores(
        document_type=DocType.BUSINESS_CARD,
        normalized_fields={
            "company": "FPT University Can Tho Campus",
        },
        validation_results={},
        ocr_blocks=[
            {
                "text": (
                    "Head of Corporate Relations Department-"
                    "FPT Univeristy Can Tho Campus"
                ),
                "confidence": 0.9668,
            },
        ],
    )
    by_name = {field.field_name: field for field in field_scores}

    assert by_name["company"].score == 0.9668


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


def test_validation_failure_without_message_blocks_auto_approval():
    field_scores = {
        field.field_name: field
        for field in _business_card_scores(
            validation_results=[
                {
                    "field_name": "email",
                    "rule": "email_format",
                    "passed": False,
                    "message": None,
                },
            ]
        )
    }

    assert field_scores["email"].score == 0.98
    assert field_scores["email"].classification == ConfidenceClass.HIGH
    assert field_scores["email"].validation_status == "failed"
    assert field_scores["email"].validation_errors == ["Validation failed: email_format"]
    assert field_scores["email"].auto_approved is False
    assert field_scores["email"].requires_manual_review is True


def test_low_confidence_validation_failure_downgrades_to_failed():
    field_scores = {
        field.field_name: field
        for field in _business_card_scores(
            validation_results=[
                {
                    "field_name": "company",
                    "rule": "business_consistency",
                    "passed": False,
                    "message": None,
                },
            ]
        )
    }

    assert field_scores["company"].score == 0.92
    assert field_scores["company"].classification == ConfidenceClass.FAILED
    assert field_scores["company"].auto_approved is False
    assert field_scores["company"].requires_manual_review is True
    assert field_scores["company"].note == (
        "Confidence inconsistency warning: inconsistent or incomplete value"
    )


@pytest.mark.asyncio
async def test_persistence_retries_after_storage_failure(monkeypatch):
    class QueryField:
        def __eq__(self, value):
            return value

    class FakeReport:
        processing_id = "PRC-TEST-RETRY"

        def __init__(self):
            self.metadata = {}
            self.insert_attempts = 0

        async def insert(self):
            self.insert_attempts += 1
            if self.insert_attempts == 1:
                raise RuntimeError("temporary storage failure")

    async def fake_find_one(*args, **kwargs):
        return None

    async def fake_sleep(*args, **kwargs):
        return None

    monkeypatch.setattr(
        confidence_service.ConfidenceReport,
        "processing_id",
        QueryField(),
        raising=False,
    )
    monkeypatch.setattr(confidence_service.ConfidenceReport, "find_one", fake_find_one)
    monkeypatch.setattr(confidence_service.asyncio, "sleep", fake_sleep)

    report = FakeReport()
    await confidence_service._persist_confidence_report(report)

    assert report.insert_attempts == 2
    assert report.metadata["persistence_attempt"] == 2


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
