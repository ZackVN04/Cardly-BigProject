from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from beanie import PydanticObjectId

from src.common.enums import DocType, ProcessingStage, StageStatus
from src.confidence.constants import (
    BUSINESS_CARD_CONTACT_FIELDS,
    BUSINESS_CARD_FIELDS,
    BUSINESS_CARD_IDENTITY_FIELDS,
)
from src.confidence.models import ConfidenceReport, ProcessingHistory
from src.exceptions import AppException
from src.mapping.models import MappedDocument
from src.ocr.models import OcrResult
from src.review.models import (
    ConfirmResponse,
    EditLog,
    FinalizedDocument,
    JsonReviewSession,
    ReviewResponse,
    ReviewStatus,
    ReviewUpdateResponse,
)


class InvalidProcessingId(AppException):
    status_code = 400
    code = "INVALID_PROCESSING_ID"
    message = "Invalid processing_id"


class ReviewSessionNotFound(AppException):
    status_code = 404
    code = "REVIEW_SESSION_NOT_FOUND"
    message = "Review session not found"


class SourceDocumentNotFound(AppException):
    status_code = 404
    code = "DOCUMENT_NOT_FOUND"
    message = "Mapped document not found for review"


class DocumentAlreadyConfirmed(AppException):
    status_code = 409
    code = "DOCUMENT_ALREADY_CONFIRMED"
    message = "Document has already been confirmed and locked"


class ReviewValidationFailed(AppException):
    status_code = 422
    code = "VALIDATION_FAILED"

    def __init__(self, validation_status: dict[str, Any]):
        self.validation_status = validation_status
        severe_errors = validation_status.get("severe_errors", [])
        missing_fields = validation_status.get("missing_required_fields", [])
        super().__init__(
            "Cannot confirm document because required data is missing or invalid. "
            f"missing_required_fields={missing_fields}; severe_errors={severe_errors}"
        )


REVIEWABLE_FIELDS = (
    "name",
    "phone",
    "email",
    "web",
    "position",
    "company",
    "address",
    "industry",
    "summary",
    "keywords",
    "highlights",
)
REQUIRED_FIELD_NAMES = set(BUSINESS_CARD_IDENTITY_FIELDS + BUSINESS_CARD_CONTACT_FIELDS)
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
URL_PATTERN = re.compile(r"^(https?://)?([a-z0-9-]+\.)+[a-z]{2,}(/.*)?$", re.IGNORECASE)


async def get_or_create_review_session(
    processing_id: str,
    user_id: PydanticObjectId | None = None,
) -> ReviewResponse:
    """Return a review session, creating it from P5/P6 data when needed."""
    _validate_processing_id(processing_id)

    session = await JsonReviewSession.find_one(
        JsonReviewSession.processing_id == processing_id
    )
    if session is None:
        session = await _create_review_session(processing_id, user_id)

    return _to_review_response(session)


async def update_review_session(
    processing_id: str,
    updates: dict[str, Any],
    edited_by: str,
) -> ReviewUpdateResponse:
    """Apply user edits, revalidate the JSON, and append audit logs."""
    _validate_processing_id(processing_id)
    if not updates:
        raise InvalidProcessingId("Request body must include at least one update")

    session = await _get_existing_session(processing_id)
    _ensure_editable(session)

    now = datetime.utcnow()
    edit_logs: list[EditLog] = []
    for field_name, new_value in updates.items():
        old_value = session.structured_data.get(field_name)
        if old_value == new_value:
            continue

        session.structured_data[field_name] = new_value
        edit_logs.append(
            EditLog(
                field_name=field_name,
                old_value=old_value,
                new_value=new_value,
                edited_by=edited_by,
                edited_at=now,
            )
        )

    if edit_logs:
        session.edit_logs.extend(edit_logs)

    session.validation_status = validate_structured_data(session.structured_data)
    session.review_status = ReviewStatus.EDITED
    session.updated_at = now
    await session.save()

    await _log_review_history(
        processing_id=processing_id,
        status=StageStatus.SUCCESS,
        details={
            "action": "edited",
            "updated_fields": list(updates.keys()),
            "validation_status": session.validation_status,
        },
    )
    return ReviewUpdateResponse(**_to_review_response(session).model_dump())


async def confirm_review_session(processing_id: str) -> ConfirmResponse:
    """Validate and lock the reviewed JSON as the final document output."""
    _validate_processing_id(processing_id)
    session = await _get_existing_session(processing_id)

    if session.review_status == ReviewStatus.CONFIRMED or session.is_locked:
        raise DocumentAlreadyConfirmed()

    validation_status = validate_structured_data(session.structured_data)
    if not validation_status["is_valid"]:
        session.validation_status = validation_status
        session.updated_at = datetime.utcnow()
        await session.save()
        raise ReviewValidationFailed(validation_status)

    now = datetime.utcnow()
    final_data = _build_final_data(session.structured_data)
    session.final_data = final_data
    session.validation_status = validation_status
    session.review_status = ReviewStatus.CONFIRMED
    session.is_locked = True
    session.confirmed_at = now
    session.updated_at = now
    await session.save()

    existing_final = await FinalizedDocument.find_one(
        FinalizedDocument.processing_id == processing_id
    )
    if existing_final is None:
        finalized = FinalizedDocument(
            processing_id=processing_id,
            user_id=session.user_id,
            doc_type=DocType.BUSINESS_CARD,
            final_data=final_data,
            final_json=final_data,
            source_review_id=session.id,
            confirmed_at=now,
        )
        await finalized.insert()

    await _log_review_history(
        processing_id=processing_id,
        status=StageStatus.SUCCESS,
        details={"action": "confirmed", "locked": True},
    )
    return ConfirmResponse(
        processing_id=processing_id,
        review_status=session.review_status,
        final_data=final_data,
        confirmed_at=now,
        is_locked=session.is_locked,
    )


def validate_structured_data(structured_data: dict[str, Any]) -> dict[str, Any]:
    """Validate review JSON while preserving null fields from failed OCR."""
    field_errors: dict[str, list[str]] = {}

    for field_name in BUSINESS_CARD_FIELDS:
        value = structured_data.get(field_name)
        errors = _validate_field(field_name, value)
        if errors:
            field_errors[field_name] = errors

    missing_required_fields = _missing_required_fields(structured_data, field_errors)
    severe_errors = _required_group_errors(structured_data, field_errors)

    return {
        "is_valid": not severe_errors,
        "missing_required_fields": missing_required_fields,
        "field_errors": field_errors,
        "severe_errors": severe_errors,
        "validated_at": datetime.utcnow().isoformat(),
    }


async def _create_review_session(
    processing_id: str,
    user_id: PydanticObjectId | None,
) -> JsonReviewSession:
    mapped_document = await MappedDocument.find_one(
        MappedDocument.processing_id == processing_id
    )
    if mapped_document is None:
        raise SourceDocumentNotFound()

    confidence_report = await ConfidenceReport.find_one(
        ConfidenceReport.processing_id == processing_id
    )
    ocr_result = await OcrResult.find_one(OcrResult.processing_id == processing_id)
    structured_data = _with_required_keys(mapped_document.normalized_fields)
    now = datetime.utcnow()

    session = JsonReviewSession(
        processing_id=processing_id,
        mapped_document_id=mapped_document.id,
        user_id=user_id or mapped_document.user_id,
        raw_ocr_output=_raw_ocr_payload(ocr_result, confidence_report),
        structured_data=structured_data,
        confidence_scores=_confidence_payload(confidence_report),
        validation_status=validate_structured_data(structured_data),
        review_status=ReviewStatus.PENDING_REVIEW,
        created_at=now,
        updated_at=now,
    )
    await session.insert()

    await _log_review_history(
        processing_id=processing_id,
        status=StageStatus.SUCCESS,
        details={"action": "review_session_created"},
    )
    return session


async def _get_existing_session(processing_id: str) -> JsonReviewSession:
    session = await JsonReviewSession.find_one(
        JsonReviewSession.processing_id == processing_id
    )
    if session is None:
        raise ReviewSessionNotFound()
    return session


def _ensure_editable(session: JsonReviewSession) -> None:
    if session.review_status == ReviewStatus.CONFIRMED or session.is_locked:
        raise DocumentAlreadyConfirmed()


def _to_review_response(session: JsonReviewSession) -> ReviewResponse:
    return ReviewResponse(
        processing_id=session.processing_id,
        raw_ocr_output=session.raw_ocr_output,
        structured_data=session.structured_data,
        confidence_scores=session.confidence_scores,
        validation_status=session.validation_status,
        review_status=session.review_status,
        edit_logs=session.edit_logs,
        final_data=session.final_data,
        is_locked=session.is_locked,
        created_at=session.created_at,
        updated_at=session.updated_at,
        confirmed_at=session.confirmed_at,
    )


def _validate_processing_id(processing_id: str) -> None:
    if not processing_id or not processing_id.strip():
        raise InvalidProcessingId()
    if len(processing_id) > 120:
        raise InvalidProcessingId()


def _with_required_keys(data: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(data or {})
    for field_name in REVIEWABLE_FIELDS:
        normalized.setdefault(field_name, None)
    return normalized


def _build_final_data(structured_data: dict[str, Any]) -> dict[str, Any]:
    return _with_required_keys(structured_data)


def _raw_ocr_payload(
    ocr_result: OcrResult | None,
    confidence_report: ConfidenceReport | None,
) -> dict[str, Any] | str | None:
    if confidence_report and confidence_report.raw_ocr_output is not None:
        return confidence_report.raw_ocr_output
    if ocr_result is None:
        return None
    return {
        "raw_text": ocr_result.raw_text,
        "blocks": [block.model_dump(mode="json") for block in ocr_result.blocks],
        "overall_confidence": ocr_result.overall_confidence,
        "ocr_engine": ocr_result.ocr_engine,
        "ocr_version": ocr_result.ocr_version,
    }


def _confidence_payload(report: ConfidenceReport | None) -> dict[str, Any]:
    if report is None:
        return {}
    return {
        "overall_score": report.overall_score,
        "classification": report.classification.value,
        "failed_fields": report.failed_fields,
        "requires_manual_review": report.flags.get("requires_manual_review", False),
        "field_scores": {
            field.field_name: {
                "value": field.value,
                "score": field.score,
                "classification": field.classification.value,
                "validation_status": field.validation_status,
                "validation_errors": field.validation_errors,
                "auto_approved": field.auto_approved,
                "requires_manual_review": field.requires_manual_review,
                "note": field.note,
            }
            for field in report.field_scores
        },
    }


def _validate_field(field_name: str, value: Any) -> list[str]:
    if _is_blank(value):
        return []
    if field_name == "email" and not EMAIL_PATTERN.match(str(value)):
        return ["Invalid email format"]
    if field_name == "phone" and len(re.sub(r"\D", "", str(value))) < 7:
        return ["Invalid phone format"]
    if field_name == "web" and not URL_PATTERN.match(str(value)):
        return ["Invalid website format"]
    return []


def _required_group_errors(
    structured_data: dict[str, Any],
    field_errors: dict[str, list[str]],
) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if not _has_valid_group_value(structured_data, BUSINESS_CARD_IDENTITY_FIELDS, field_errors):
        errors.append(
            {
                "field_name": "identity",
                "rule": "required_group",
                "message": "At least one valid identity field is required: name or company",
            }
        )
    if not _has_valid_group_value(structured_data, BUSINESS_CARD_CONTACT_FIELDS, field_errors):
        errors.append(
            {
                "field_name": "contact_method",
                "rule": "required_group",
                "message": "At least one valid contact field is required: email, phone, or web",
            }
        )
    return errors


def _missing_required_fields(
    structured_data: dict[str, Any],
    field_errors: dict[str, list[str]],
) -> list[str]:
    missing: list[str] = []
    if not _has_valid_group_value(structured_data, BUSINESS_CARD_IDENTITY_FIELDS, field_errors):
        missing.extend(BUSINESS_CARD_IDENTITY_FIELDS)
    if not _has_valid_group_value(structured_data, BUSINESS_CARD_CONTACT_FIELDS, field_errors):
        missing.extend(BUSINESS_CARD_CONTACT_FIELDS)
    return missing


def _has_valid_group_value(
    structured_data: dict[str, Any],
    fields: tuple[str, ...],
    field_errors: dict[str, list[str]],
) -> bool:
    return any(
        not _is_blank(structured_data.get(field_name))
        and field_name not in field_errors
        for field_name in fields
    )


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


async def _log_review_history(
    processing_id: str,
    status: StageStatus,
    details: dict[str, Any],
) -> None:
    history = ProcessingHistory(
        processing_id=processing_id,
        stage=ProcessingStage.REVIEW,
        status=status,
        details=details,
    )
    await history.insert()
