from __future__ import annotations

from time import perf_counter
from typing import Any

from src.common.enums import DocType, ProcessingStage, StageStatus
from src.confidence.config import confidence_settings
from src.confidence.constants import (
    BUSINESS_CARD_CONTACT_FIELDS,
    BUSINESS_CARD_FIELDS,
    BUSINESS_CARD_IDENTITY_FIELDS,
    BUSINESS_CARD_SCHEMA,
)
from src.confidence.exceptions import (
    DocumentNotFound,
    ScoringFailed,
    UnsupportedDocumentType,
)
from src.confidence.models import (
    ConfidenceClass,
    ConfidenceReport,
    FieldConfidence,
    OverallClassification,
    ProcessingHistory,
)
from src.confidence.schemas import (
    ConfidenceResponse,
    DocumentFullStateResponse,
    FieldConfidenceSchema,
)
from src.intake.models import UploadedImage
from src.mapping.models import MappedDocument
from src.ocr.models import AiVisionResult, OcrResult


def classify_field(score: float) -> ConfidenceClass:
    """Classify one extracted field by OCR confidence score."""
    if score >= confidence_settings.HIGH_THRESHOLD:
        return ConfidenceClass.HIGH
    if score >= confidence_settings.LOW_THRESHOLD:
        return ConfidenceClass.LOW
    return ConfidenceClass.FAILED


def classify_overall(score: float) -> OverallClassification:
    """Classify the whole document for processing history and review state."""
    if score >= confidence_settings.HIGH_THRESHOLD:
        return OverallClassification.SUCCESS
    if score >= confidence_settings.LOW_THRESHOLD:
        return OverallClassification.PARTIAL_SUCCESS
    return OverallClassification.FAILED


async def score_document(processing_id: str) -> ConfidenceReport:
    """Score mapped fields for one document and persist the P6 report."""
    started = perf_counter()
    mapped_document = await MappedDocument.find_one(MappedDocument.processing_id == processing_id)
    if mapped_document is None:
        raise DocumentNotFound(f"Mapped document not found for processing_id={processing_id}")
    _ensure_business_card(mapped_document.doc_type)

    ocr_result = await OcrResult.find_one(OcrResult.processing_id == processing_id)
    if ocr_result is None:
        raise DocumentNotFound(f"OCR result not found for processing_id={processing_id}")

    try:
        field_scores = build_field_scores(
            document_type=mapped_document.doc_type,
            normalized_fields=mapped_document.normalized_fields,
            validation_results=mapped_document.validation_results,
            ocr_blocks=[block.model_dump() for block in ocr_result.blocks],
            field_block_refs=mapped_document.field_block_refs,
        )
        overall_score = calculate_overall_score(mapped_document.doc_type, field_scores)
        classification = classify_overall(overall_score)
        failed_fields = [
            field.field_name
            for field in field_scores
            if field.classification == ConfidenceClass.FAILED
        ]
        requires_manual_review = any(field.requires_manual_review for field in field_scores)

        existing = await ConfidenceReport.find_one(
            ConfidenceReport.processing_id == processing_id
        )
        if existing is not None:
            await existing.delete()

        report = ConfidenceReport(
            processing_id=processing_id,
            mapped_document_id=mapped_document.id,
            document_type=mapped_document.doc_type,
            raw_ocr_output=ocr_result.model_dump(mode="json"),
            normalized_fields=mapped_document.normalized_fields,
            validation_results=[
                result.model_dump(mode="json")
                for result in mapped_document.validation_results
            ],
            field_scores=field_scores,
            overall_score=overall_score,
            classification=classification,
            flags={"requires_manual_review": requires_manual_review},
            failed_fields=failed_fields,
            metadata={"business_card_schema": BUSINESS_CARD_SCHEMA},
        )
        await report.insert()

        await log_stage_history(
            processing_id=processing_id,
            stage=ProcessingStage.CONFIDENCE_SCORING,
            status=_stage_status_from_overall(classification),
            details={
                "overall_score": overall_score,
                "document_type": mapped_document.doc_type.value,
                "requires_manual_review": requires_manual_review,
            },
            duration_ms=int((perf_counter() - started) * 1000),
        )
        return report
    except DocumentNotFound:
        raise
    except Exception as exc:
        raise ScoringFailed(str(exc)) from exc


def build_field_scores(
    *,
    document_type: DocType | str,
    normalized_fields: dict[str, Any],
    validation_results: Any,
    ocr_blocks: list[dict[str, Any]],
    field_block_refs: dict[str, list[str]] | None = None,
) -> list[FieldConfidence]:
    """Create Business Card field-level confidence records without touching the database."""
    doc_type = _coerce_doc_type(document_type)
    _ensure_business_card(doc_type)
    return [
        _score_one_field(
            field_name=field_name,
            value=normalized_fields.get(field_name),
            validation_results=validation_results,
            ocr_blocks=ocr_blocks,
            block_refs=(field_block_refs or {}).get(field_name, []),
        )
        for field_name in BUSINESS_CARD_FIELDS
    ]


def calculate_overall_score(
    document_type: DocType | str,
    field_scores: list[FieldConfidence],
) -> float:
    """Calculate Business Card overall confidence from required groups."""
    doc_type = _coerce_doc_type(document_type)
    _ensure_business_card(doc_type)
    if not field_scores:
        return 0.0

    by_name = {field.field_name: field.score for field in field_scores}
    identity_score = max(
        (by_name.get(field, 0.0) for field in BUSINESS_CARD_IDENTITY_FIELDS),
        default=0.0,
    )
    contact_score = max(
        (by_name.get(field, 0.0) for field in BUSINESS_CARD_CONTACT_FIELDS),
        default=0.0,
    )
    return _round_score((identity_score + contact_score) / 2)


async def log_stage_history(
    processing_id: str,
    stage: ProcessingStage,
    status: StageStatus,
    details: dict[str, Any] | None = None,
    duration_ms: int | None = None,
) -> ProcessingHistory:
    """Append one processing-history row for audit and troubleshooting."""
    history = ProcessingHistory(
        processing_id=processing_id,
        stage=stage,
        status=status,
        details=details or {},
        duration_ms=duration_ms,
    )
    await history.insert()
    return history


async def get_full_document_state(processing_id: str) -> DocumentFullStateResponse:
    """Return all document data P7 needs for JSON review."""
    mapped_document = await MappedDocument.find_one(MappedDocument.processing_id == processing_id)
    if mapped_document is None:
        raise DocumentNotFound(f"Mapped document not found for processing_id={processing_id}")
    _ensure_business_card(mapped_document.doc_type)

    confidence_report = await ConfidenceReport.find_one(
        ConfidenceReport.processing_id == processing_id
    )
    uploaded_image = await UploadedImage.find_one(UploadedImage.processing_id == processing_id)
    ocr_result = await OcrResult.find_one(OcrResult.processing_id == processing_id)
    vision_result = await AiVisionResult.find_one(
        AiVisionResult.processing_id == processing_id
    )
    history = await ProcessingHistory.find(
        ProcessingHistory.processing_id == processing_id
    ).sort("+created_at").to_list()

    confidence = _confidence_response(confidence_report) if confidence_report else None
    validation = {
        "missing_required_fields": mapped_document.missing_required_fields,
        "validation_results": [
            result.model_dump(mode="json")
            for result in mapped_document.validation_results
        ],
    }

    return DocumentFullStateResponse(
        processing_id=processing_id,
        document_type=mapped_document.doc_type.value,
        status="ready_for_review" if confidence_report else "processing",
        doc_type=mapped_document.doc_type.value,
        doc_type_confidence=vision_result.doc_type_confidence if vision_result else None,
        uploaded_at=uploaded_image.uploaded_at.isoformat() if uploaded_image else None,
        processed_at=confidence_report.scored_at.isoformat() if confidence_report else None,
        raw_ocr_output=ocr_result.raw_text if ocr_result else None,
        normalized_fields=mapped_document.normalized_fields,
        extracted_fields=mapped_document.extracted_fields,
        validation_results=validation["validation_results"],
        confidence_report=confidence,
        confidence=confidence,
        validation=validation,
        processing_history=[
            {
                "stage": item.stage.value,
                "status": item.status.value,
                "details": item.details,
                "duration_ms": item.duration_ms,
                "created_at": item.created_at.isoformat(),
            }
            for item in history
        ],
    )


def _score_one_field(
    *,
    field_name: str,
    value: Any,
    validation_results: Any,
    ocr_blocks: list[dict[str, Any]],
    block_refs: list[str],
) -> FieldConfidence:
    validation_status, validation_errors = _validation_for_field(
        field_name,
        validation_results,
    )
    score = _field_score(value, ocr_blocks, block_refs)
    classification = classify_field(score)
    validation_passed = validation_status == "passed"
    auto_approved = classification == ConfidenceClass.HIGH and validation_passed
    requires_manual_review = not auto_approved

    note = None
    if classification == ConfidenceClass.LOW:
        note = "Below high-confidence threshold"
    if classification == ConfidenceClass.FAILED:
        note = "Manual review required"
    if not validation_passed:
        note = "Validation failed; automatic approval blocked"

    return FieldConfidence(
        field_name=field_name,
        value=value,
        score=score,
        classification=classification,
        validation_status=validation_status,
        validation_errors=validation_errors,
        auto_approved=auto_approved,
        requires_manual_review=requires_manual_review,
        note=note,
    )


def _field_score(
    value: Any,
    ocr_blocks: list[dict[str, Any]],
    block_refs: list[str],
) -> float:
    if value in (None, ""):
        return 0.0

    matching_blocks = _blocks_by_ref(ocr_blocks, block_refs)
    if not matching_blocks:
        matching_blocks = _blocks_by_text(ocr_blocks, str(value))
    if not matching_blocks:
        return 0.0

    scores = [float(block.get("confidence", 0.0)) for block in matching_blocks]
    return _round_score(sum(scores) / len(scores))


def _blocks_by_ref(
    ocr_blocks: list[dict[str, Any]],
    block_refs: list[str],
) -> list[dict[str, Any]]:
    if not block_refs:
        return []
    refs = set(block_refs)
    return [block for block in ocr_blocks if block.get("id") in refs]


def _blocks_by_text(
    ocr_blocks: list[dict[str, Any]],
    value: str,
) -> list[dict[str, Any]]:
    normalized_value = _normalize_for_match(value)
    exact = [
        block
        for block in ocr_blocks
        if _normalize_for_match(str(block.get("text", ""))) == normalized_value
    ]
    if exact:
        return exact
    return [
        block
        for block in ocr_blocks
        if normalized_value and normalized_value in _normalize_for_match(str(block.get("text", "")))
    ]


def _validation_for_field(field_name: str, validation_results: Any) -> tuple[str, list[str]]:
    if not validation_results:
        return "passed", []

    if isinstance(validation_results, dict):
        result = validation_results.get(field_name)
        if result is None:
            return "passed", []
        status = str(result.get("status", "passed"))
        errors = list(result.get("errors", []))
        return status, errors

    field_results = [
        item
        for item in validation_results
        if _get_attr_or_key(item, "field_name") == field_name
    ]
    failed_messages = [
        _get_attr_or_key(item, "message")
        for item in field_results
        if _get_attr_or_key(item, "passed") is False
    ]
    errors = [message for message in failed_messages if message]
    return ("failed", errors) if errors else ("passed", [])


def _confidence_response(report: ConfidenceReport | None) -> ConfidenceResponse | None:
    if report is None:
        return None
    return ConfidenceResponse(
        overall_score=report.overall_score,
        classification=report.classification.value,
        field_scores=[
            FieldConfidenceSchema(
                field_name=field.field_name,
                value=field.value,
                score=field.score,
                classification=field.classification.value,
                validation_status=field.validation_status,
                validation_errors=field.validation_errors,
                auto_approved=field.auto_approved,
                requires_manual_review=field.requires_manual_review,
                note=field.note,
            )
            for field in report.field_scores
        ],
        failed_fields=report.failed_fields,
        requires_manual_review=report.flags.get("requires_manual_review", False),
    )


def _stage_status_from_overall(classification: OverallClassification) -> StageStatus:
    if classification == OverallClassification.SUCCESS:
        return StageStatus.SUCCESS
    if classification == OverallClassification.PARTIAL_SUCCESS:
        return StageStatus.PARTIAL_SUCCESS
    return StageStatus.FAILED


def _coerce_doc_type(document_type: DocType | str) -> DocType:
    if isinstance(document_type, DocType):
        return document_type
    return DocType(document_type)


def _ensure_business_card(document_type: DocType) -> None:
    if document_type != DocType.BUSINESS_CARD:
        raise UnsupportedDocumentType()


def _get_attr_or_key(item: Any, key: str) -> Any:
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key, None)


def _normalize_for_match(value: str) -> str:
    return " ".join(value.lower().split())


def _round_score(score: float) -> float:
    return round(max(0.0, min(1.0, score)), 4)
