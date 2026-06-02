from datetime import datetime
from types import SimpleNamespace
from typing import Any, ClassVar

import pytest
from beanie import PydanticObjectId

from src.common.enums import DocType
from src.confidence.models import (
    ConfidenceClass,
    FieldConfidence,
    OverallClassification,
)
from src.mapping.models import MappedDocument
from src.ocr.models import OcrBlock, OcrResult
from src.review import service
from src.review.models import (
    FinalizedDocument,
    JsonReviewSession,
    ReviewStatus,
)

pytestmark = pytest.mark.asyncio


class _QueryField:
    def __eq__(self, value: Any) -> Any:
        return value


class _FakeFind:
    def __init__(self, value: Any):
        self.value = value

    async def __await_find_one__(self) -> Any:
        return self.value

    def __await__(self):
        return self.__await_find_one__().__await__()


class _SavedSession(JsonReviewSession):
    save_calls: int = 0
    insert_calls: int = 0

    async def save(self) -> None:
        self.save_calls += 1

    async def insert(self) -> None:
        self.insert_calls += 1


class _SavedFinal(FinalizedDocument):
    inserted_docs: ClassVar[list[FinalizedDocument]] = []

    async def insert(self) -> None:
        self.inserted_docs.append(self)


class _SavedHistory:
    inserted: list[Any] = []

    def __init__(self, **kwargs: Any):
        self.kwargs = kwargs

    async def insert(self) -> None:
        self.inserted.append(self.kwargs)


def _object_id() -> PydanticObjectId:
    return PydanticObjectId()


def _valid_structured_data() -> dict[str, Any]:
    return {
        "name": "Nguyen Van A",
        "phone": "0900000000",
        "email": "a@example.com",
        "web": "https://example.com",
        "position": "Backend Engineer",
        "company": "Cardly",
        "industry": None,
        "summary": None,
        "keywords": [],
        "highlights": [],
    }


def _session(
    *,
    processing_id: str = "PRC-TEST-001",
    structured_data: dict[str, Any] | None = None,
    status: ReviewStatus = ReviewStatus.PENDING_REVIEW,
    locked: bool = False,
) -> _SavedSession:
    return _SavedSession.model_construct(
        id=_object_id(),
        processing_id=processing_id,
        mapped_document_id=_object_id(),
        user_id=_object_id(),
        raw_ocr_output={"raw_text": "Nguyen Van A"},
        structured_data=structured_data or _valid_structured_data(),
        confidence_scores={"overall_score": 0.96},
        validation_status={},
        review_status=status,
        edit_logs=[],
        is_locked=locked,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


def _mapped_document(processing_id: str = "PRC-TEST-001") -> MappedDocument:
    return MappedDocument.model_construct(
        id=_object_id(),
        processing_id=processing_id,
        doc_type=DocType.BUSINESS_CARD,
        user_id=_object_id(),
        extracted_fields=_valid_structured_data(),
        normalized_fields=_valid_structured_data(),
        validation_results=[],
        missing_required_fields=[],
        mapper_version="test",
    )


def _confidence_report() -> Any:
    return type(
        "ConfidenceReportStub",
        (),
        {
            "raw_ocr_output": {"raw_text": "Nguyen Van A\n0900000000"},
            "overall_score": 0.96,
            "classification": OverallClassification.SUCCESS,
            "failed_fields": [],
            "flags": {"requires_manual_review": False},
            "field_scores": [
                FieldConfidence(
                    field_name="name",
                    value="Nguyen Van A",
                    score=0.98,
                    classification=ConfidenceClass.HIGH,
                    auto_approved=True,
                )
            ],
        },
    )()


def _ocr_result(processing_id: str = "PRC-TEST-001") -> OcrResult:
    return OcrResult.model_construct(
        id=_object_id(),
        processing_id=processing_id,
        preprocessed_image_id=_object_id(),
        ocr_engine="paddle",
        raw_text="Nguyen Van A",
        blocks=[OcrBlock(id="b1", text="Nguyen Van A", bbox=[], confidence=0.98)],
        overall_confidence=0.98,
        ocr_version="test",
    )


def _patch_find_one(monkeypatch: pytest.MonkeyPatch, model: Any, value: Any) -> None:
    monkeypatch.setattr(model, "processing_id", _QueryField(), raising=False)
    monkeypatch.setattr(model, "find_one", lambda *args, **kwargs: _FakeFind(value))
    monkeypatch.setattr(
        model,
        "get_settings",
        classmethod(lambda cls: SimpleNamespace(motor_collection=None)),
    )


def _patch_common_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    _SavedFinal.inserted_docs = []
    _SavedHistory.inserted = []
    monkeypatch.setattr(service, "ProcessingHistory", _SavedHistory)
    monkeypatch.setattr(service, "FinalizedDocument", _SavedFinal)
    monkeypatch.setattr(_SavedFinal, "processing_id", _QueryField(), raising=False)


def test_validate_accepts_valid_business_card_data() -> None:
    result = service.validate_structured_data(_valid_structured_data())

    assert result["is_valid"] is True
    assert result["missing_required_fields"] == []
    assert result["severe_errors"] == []


def test_validate_rejects_missing_identity_and_contact_groups() -> None:
    result = service.validate_structured_data({})

    assert result["is_valid"] is False
    assert "name" in result["missing_required_fields"]
    assert "email" in result["missing_required_fields"]
    assert {error["field_name"] for error in result["severe_errors"]} == {
        "identity",
        "contact_method",
    }


def test_validate_rejects_invalid_required_email_and_phone() -> None:
    result = service.validate_structured_data(
        {"name": "Nguyen Van A", "email": "bad-email", "phone": "12"}
    )

    assert result["is_valid"] is False
    assert "email" in result["field_errors"]
    assert "phone" in result["field_errors"]


def test_validate_warns_optional_web_but_does_not_block_confirm() -> None:
    result = service.validate_structured_data(
        {"name": "Nguyen Van A", "phone": "0900000000", "web": "not a website"}
    )

    assert result["is_valid"] is True
    assert result["field_errors"]["web"] == ["Invalid website format"]


async def test_get_review_creates_session_from_pipeline_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: list[JsonReviewSession] = []

    _patch_find_one(monkeypatch, JsonReviewSession, None)
    _patch_find_one(monkeypatch, MappedDocument, _mapped_document())
    _patch_find_one(monkeypatch, service.ConfidenceReport, _confidence_report())
    _patch_find_one(monkeypatch, service.OcrResult, _ocr_result())
    _patch_common_writes(monkeypatch)

    async def fake_insert(self: JsonReviewSession) -> None:
        created.append(self)

    monkeypatch.setattr(JsonReviewSession, "insert", fake_insert)

    response = await service.get_or_create_review_session(
        "PRC-TEST-001",
        user_id=_object_id(),
    )

    assert response.processing_id == "PRC-TEST-001"
    assert response.review_status == ReviewStatus.PENDING_REVIEW
    assert response.structured_data["company"] == "Cardly"
    assert response.structured_data["industry"] is None
    assert response.raw_ocr_output == {"raw_text": "Nguyen Van A\n0900000000"}
    assert created


async def test_get_review_returns_existing_session(monkeypatch: pytest.MonkeyPatch) -> None:
    existing = _session()
    _patch_find_one(monkeypatch, JsonReviewSession, existing)

    response = await service.get_or_create_review_session("PRC-TEST-001")

    assert response.processing_id == existing.processing_id
    assert response.structured_data == existing.structured_data


async def test_get_review_missing_source_document_returns_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_find_one(monkeypatch, JsonReviewSession, None)
    _patch_find_one(monkeypatch, MappedDocument, None)

    with pytest.raises(service.SourceDocumentNotFound) as exc:
        await service.get_or_create_review_session("PRC-UNKNOWN")

    assert exc.value.status_code == 404


async def test_get_review_invalid_processing_id_returns_400() -> None:
    with pytest.raises(service.InvalidProcessingId) as exc:
        await service.get_or_create_review_session("")

    assert exc.value.status_code == 400


async def test_patch_updates_one_field_and_writes_edit_log(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _session()
    _patch_find_one(monkeypatch, JsonReviewSession, session)
    _patch_common_writes(monkeypatch)

    response = await service.update_review_session(
        "PRC-TEST-001",
        {"name": "Nguyen Van B"},
        edited_by="user-1",
    )

    assert response.structured_data["name"] == "Nguyen Van B"
    assert response.review_status == ReviewStatus.EDITED
    assert response.edit_logs[-1].field_name == "name"
    assert response.edit_logs[-1].old_value == "Nguyen Van A"
    assert response.edit_logs[-1].new_value == "Nguyen Van B"
    assert response.edit_logs[-1].edited_by == "user-1"
    assert response.edit_logs[-1].edited_at is not None


async def test_patch_updates_multiple_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _session()
    _patch_find_one(monkeypatch, JsonReviewSession, session)
    _patch_common_writes(monkeypatch)

    response = await service.update_review_session(
        "PRC-TEST-001",
        {"name": "Nguyen Van B", "phone": "0911111111"},
        edited_by="user-1",
    )

    assert response.structured_data["name"] == "Nguyen Van B"
    assert response.structured_data["phone"] == "0911111111"
    assert [log.field_name for log in response.edit_logs] == ["name", "phone"]


async def test_patch_null_keeps_field(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _session()
    _patch_find_one(monkeypatch, JsonReviewSession, session)
    _patch_common_writes(monkeypatch)

    response = await service.update_review_session(
        "PRC-TEST-001",
        {"company": None},
        edited_by="user-1",
    )

    assert "company" in response.structured_data
    assert response.structured_data["company"] is None


async def test_patch_invalid_email_updates_validation_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _session()
    _patch_find_one(monkeypatch, JsonReviewSession, session)
    _patch_common_writes(monkeypatch)

    response = await service.update_review_session(
        "PRC-TEST-001",
        {"email": "bad-email"},
        edited_by="user-1",
    )

    assert response.validation_status["is_valid"] is True
    assert "email" in response.validation_status["field_errors"]


async def test_patch_empty_updates_returns_400(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(service.InvalidProcessingId) as exc:
        await service.update_review_session("PRC-TEST-001", {}, edited_by="user-1")

    assert exc.value.status_code == 400


async def test_patch_missing_session_returns_404(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_find_one(monkeypatch, JsonReviewSession, None)

    with pytest.raises(service.ReviewSessionNotFound) as exc:
        await service.update_review_session(
            "PRC-UNKNOWN",
            {"name": "Nguyen Van B"},
            edited_by="user-1",
        )

    assert exc.value.status_code == 404


async def test_patch_confirmed_document_returns_409(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _session(status=ReviewStatus.CONFIRMED)
    _patch_find_one(monkeypatch, JsonReviewSession, session)

    with pytest.raises(service.DocumentAlreadyConfirmed) as exc:
        await service.update_review_session(
            "PRC-TEST-001",
            {"name": "Blocked"},
            edited_by="user-1",
        )

    assert exc.value.status_code == 409


async def test_patch_locked_document_returns_409(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _session(locked=True)
    _patch_find_one(monkeypatch, JsonReviewSession, session)

    with pytest.raises(service.DocumentAlreadyConfirmed):
        await service.update_review_session(
            "PRC-TEST-001",
            {"name": "Blocked"},
            edited_by="user-1",
        )


async def test_patch_same_value_does_not_write_edit_log(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _session()
    _patch_find_one(monkeypatch, JsonReviewSession, session)
    _patch_common_writes(monkeypatch)

    response = await service.update_review_session(
        "PRC-TEST-001",
        {"name": "Nguyen Van A"},
        edited_by="user-1",
    )

    assert response.edit_logs == []
    assert response.structured_data["name"] == "Nguyen Van A"


async def test_confirm_success_creates_final_data_and_locks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _session(status=ReviewStatus.EDITED)
    _patch_find_one(monkeypatch, JsonReviewSession, session)
    _patch_find_one(monkeypatch, _SavedFinal, None)
    _patch_common_writes(monkeypatch)

    response = await service.confirm_review_session("PRC-TEST-001")

    assert response.review_status == ReviewStatus.CONFIRMED
    assert response.is_locked is True
    assert response.final_data == service._build_final_data(session.structured_data)
    assert session.review_status == ReviewStatus.CONFIRMED
    assert session.is_locked is True
    assert session.confirmed_at is not None
    assert len(_SavedFinal.inserted_docs) == 1
    assert _SavedFinal.inserted_docs[0].final_json == response.final_data


async def test_confirm_pending_review_without_edits_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _session(status=ReviewStatus.PENDING_REVIEW)
    _patch_find_one(monkeypatch, JsonReviewSession, session)
    _patch_find_one(monkeypatch, _SavedFinal, None)
    _patch_common_writes(monkeypatch)

    response = await service.confirm_review_session("PRC-TEST-001")

    assert response.review_status == ReviewStatus.CONFIRMED


async def test_confirm_missing_required_fields_returns_422(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _session(structured_data={"name": None, "company": None})
    _patch_find_one(monkeypatch, JsonReviewSession, session)

    with pytest.raises(service.ReviewValidationFailed) as exc:
        await service.confirm_review_session("PRC-TEST-001")

    assert exc.value.status_code == 422
    assert session.review_status == ReviewStatus.PENDING_REVIEW


async def test_confirm_invalid_email_returns_422(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _session(
        structured_data={"name": "Nguyen Van A", "email": "bad-email"}
    )
    _patch_find_one(monkeypatch, JsonReviewSession, session)

    with pytest.raises(service.ReviewValidationFailed):
        await service.confirm_review_session("PRC-TEST-001")


async def test_confirm_invalid_phone_returns_422(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _session(structured_data={"name": "Nguyen Van A", "phone": "12"})
    _patch_find_one(monkeypatch, JsonReviewSession, session)

    with pytest.raises(service.ReviewValidationFailed):
        await service.confirm_review_session("PRC-TEST-001")


async def test_confirm_missing_session_returns_404(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_find_one(monkeypatch, JsonReviewSession, None)

    with pytest.raises(service.ReviewSessionNotFound) as exc:
        await service.confirm_review_session("PRC-UNKNOWN")

    assert exc.value.status_code == 404


async def test_confirm_invalid_processing_id_returns_400() -> None:
    with pytest.raises(service.InvalidProcessingId):
        await service.confirm_review_session("")


async def test_confirm_already_confirmed_returns_409(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _session(status=ReviewStatus.CONFIRMED, locked=True)
    _patch_find_one(monkeypatch, JsonReviewSession, session)

    with pytest.raises(service.DocumentAlreadyConfirmed) as exc:
        await service.confirm_review_session("PRC-TEST-001")

    assert exc.value.status_code == 409


async def test_confirm_uses_existing_finalized_document_without_duplicate_insert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _session(status=ReviewStatus.EDITED)
    existing_final = _SavedFinal.model_construct(
        id=_object_id(),
        processing_id="PRC-TEST-001",
        user_id=session.user_id,
        doc_type=DocType.BUSINESS_CARD,
        final_data=_valid_structured_data(),
        final_json=_valid_structured_data(),
        source_review_id=session.id,
    )
    _patch_find_one(monkeypatch, JsonReviewSession, session)
    _patch_find_one(monkeypatch, _SavedFinal, existing_final)
    _patch_common_writes(monkeypatch)

    await service.confirm_review_session("PRC-TEST-001")

    assert _SavedFinal.inserted_docs == []
