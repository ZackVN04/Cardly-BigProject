import asyncio

from src.pipeline.exceptions import PipelineFailed


async def run_pipeline(processing_id: str) -> None:
    """Orchestrate P3 → P4 → P5 → P6 in sequence (P4 OCR+Vision run in parallel)."""
    from src.preprocess import service as preprocess_service
    from src.ocr import service as ocr_service
    from src.mapping import service as mapping_service
    from src.confidence import service as confidence_service

    try:
        # P3 — preprocess
        preprocessed = await preprocess_service.normalize(processing_id)

        # P4 — OCR + Vision in parallel
        ocr_result, vision_result = await asyncio.gather(
            ocr_service.run_ocr(processing_id, preprocessed.processed_storage_path),
            ocr_service.run_vision(processing_id, preprocessed.processed_storage_path),
        )

        # P5 — field mapping
        mapped = await mapping_service.map_document_fields(
            processing_id=processing_id,
            doc_type=vision_result.doc_type,
            ocr_result=ocr_result.model_dump(),
            vision_result=vision_result.model_dump(),
            user_id=str(preprocessed.source_image_id),
        )

        # P6 — confidence scoring
        await confidence_service.score_document(processing_id)

        await _update_status(processing_id, "ready_for_review")

    except Exception as exc:
        await _update_status(processing_id, "failed")
        raise PipelineFailed(str(exc)) from exc


async def _update_status(processing_id: str, status: str) -> None:
    from src.intake.models import UploadedImage
    doc = await UploadedImage.find_one(UploadedImage.processing_id == processing_id)
    if doc:
        doc.status = status  # type: ignore[assignment]
        await doc.save()
