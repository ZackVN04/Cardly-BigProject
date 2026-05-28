from fastapi import APIRouter, Depends, Query, status, UploadFile
from fastapi.responses import StreamingResponse

from src.auth.models import User
from src.auth.dependencies import get_current_user
from . import service, schemas, dependencies, utils

# ---------------------------------------------------------------------------
# Dev placeholder: replaced by Depends(get_current_user) once P1 (Auth) is done.
# ---------------------------------------------------------------------------
MOCK_USER_ID = "MOCK_USER"

router = APIRouter()


@router.get("/health", tags=["health"])
async def intake_health() -> dict:
    return {"module": "intake", "status": "ready"}


@router.post(
    "",
    response_model=schemas.UploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload 1 or 2 document images for OCR processing",
)
async def upload_document(
    file: UploadFile = Depends(dependencies.valid_upload_file),
    file2: UploadFile | None = Depends(dependencies.valid_optional_upload_file),
    current_user: User = Depends(get_current_user),
) -> schemas.UploadResponse:
    """Upload 1 or 2 images in a single request.

    Both files receive the same ``processing_id`` and are stored as separate
    MongoDB documents.  On GCS they share the same folder:
    ``{processing_id}/{filename}``.
    A single pipeline task is enqueued for the whole submission.
    """
    processing_id = utils.generate_processing_id()

    files_to_process = [f for f in [file, file2] if f is not None]

    entries: list[schemas.FileEntry] = []
    for f in files_to_process:
        doc, url = await service.ingest_single_file(f, processing_id)
        entries.append(
            schemas.FileEntry(original_filename=doc.original_filename, file_url=url)
        )

    # Enqueue one pipeline task per submission (not per file)
    # await service.enqueue_pipeline_task(processing_id)

    return schemas.UploadResponse(processing_id=processing_id, files=entries)



@router.get(
    "",
    response_model=schemas.DocumentListResponse,
    summary="List documents uploaded by the current user",
)
async def list_documents(
    current_user: User = Depends(get_current_user),
    skip: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=20, ge=1, le=100, description="Max records to return"),
    status: str | None = Query(default=None, description="Filter by document status"),
) -> schemas.DocumentListResponse:
    """Return a paginated list of documents owned by the authenticated user."""
    docs = await service.list_documents(
        user_id=str(current_user.id),
        skip=skip,
        limit=limit,
        status_filter=status,
    )

    items = [
        schemas.DocumentSummary(
            processing_id=doc.processing_id,
            original_filename=doc.original_filename,
            mime_type=doc.mime_type,
            file_size=doc.file_size,
            status=doc.status.value,
            uploaded_at=doc.uploaded_at,
            file_urls=[doc.file_url] if doc.file_url else [],
        )
        for doc in docs
    ]

    return schemas.DocumentListResponse(
        items=items,
        total=len(items),
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{doc_id}/image",
    summary="Get signed URLs for the original uploaded image(s)",
)
async def get_document_image(doc_id: str) -> dict[str, list[str]]:
    """Return a list of signed GCS URLs for the original images.
    If a multi-upload occurred, both URLs are returned.
    """
    urls = await service.get_image_urls(
        processing_id=doc_id,
        user_id=MOCK_USER_ID,
    )
    return {"urls": urls}


@router.delete(
    "/{doc_id}",
    response_model=schemas.DeleteResponse,
    summary="Soft-delete a document",
)
async def delete_document(doc_id: str) -> schemas.DeleteResponse:
    """Soft-delete a document by setting its status to ``REJECTED_INVALID``."""
    await service.soft_delete(processing_id=doc_id, user_id=MOCK_USER_ID)
    return schemas.DeleteResponse(processing_id=doc_id)
