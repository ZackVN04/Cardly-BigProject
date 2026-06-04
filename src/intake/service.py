from __future__ import annotations

import io
from datetime import datetime, timedelta
from typing import Iterator, TYPE_CHECKING

if TYPE_CHECKING:
    from .models import UploadedImage

from fastapi import HTTPException, status, UploadFile
from google.cloud import storage
from PIL import Image

from . import config as intake_cfg
from . import utils
from src.config import settings as global_cfg

async def validate_mime(mime_type: str) -> None:
    if mime_type not in intake_cfg.intake_settings.ALLOWED_MIMES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"MIME type {mime_type} not allowed",
        )


async def validate_size(content_length: int) -> None:
    max_bytes = intake_cfg.intake_settings.MAX_SIZE_MB * 1024 * 1024
    if content_length > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds max size of {intake_cfg.intake_settings.MAX_SIZE_MB} MB",
        )


async def detect_corrupted(file_content: bytes, mime_type: str) -> None:
    if mime_type.startswith("image/"):
        try:
            img = Image.open(io.BytesIO(file_content))
            img.verify()
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded image is corrupted or unreadable",
            )


async def validate_file_format(file_content: bytes, mime_type: str) -> None:
    """Validate that the uploaded bytes match the declared MIME type."""
    if mime_type.startswith("image/"):
        try:
            Image.open(io.BytesIO(file_content)).verify()
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File content does not match declared image MIME type",
            )



from fastapi.concurrency import run_in_threadpool
from .exceptions import DuplicateFile

async def dedupe_by_hash(file_hash: str, user_id: str) -> None:
    """Raise 409 if a document with the same SHA-256 hash already exists in DB for this user."""
    # Local import to avoid circular dependency with models.py
    from src.intake.models import UploadedImage, ImageStatus
    from beanie import PydanticObjectId

    criteria = [
        UploadedImage.file_hash_sha256 == file_hash,
        UploadedImage.status != ImageStatus.REJECTED_DUPLICATE
    ]

    if user_id != "MOCK_USER":
        try:
            user_oid = PydanticObjectId(user_id)
            criteria.append(UploadedImage.user_id == user_oid)
        except Exception:
            pass

    existing = await UploadedImage.find_one(*criteria)
    if existing is not None:
        raise DuplicateFile()


async def get_image_dimensions(file_content: bytes) -> tuple[int | None, int | None]:
    """Return (width, height) of an image byte stream."""
    try:
        with Image.open(io.BytesIO(file_content)) as img:
            return img.width, img.height
    except Exception:
        return None, None


def _get_storage_client() -> storage.Client:
    """Return an initialized Google Cloud Storage client."""
    if global_cfg.gcs_credentials:
        return storage.Client(credentials=global_cfg.gcs_credentials)
    return storage.Client()


async def save_to_storage(file_content: bytes, filename: str, processing_id: str, user_id: str) -> str:
    """Upload the file bytes to Google Cloud Storage and return a signed URL."""
    client = await run_in_threadpool(_get_storage_client)
    storage_path = f"{user_id}/{processing_id}/{filename}"
    bucket = client.bucket(intake_cfg.intake_settings.GCS_BUCKET_NAME)
    blob = bucket.blob(storage_path)
    
    # Run the blocking upload in a threadpool to avoid hanging the event loop
    await run_in_threadpool(blob.upload_from_string, file_content)

    return await _generate_signed_url(storage_path, client=client)


async def _generate_signed_url(storage_path: str, client: storage.Client | None = None) -> str:
    """Generate a signed URL for a given storage path.
    Client can be provided to reuse it in loops.
    """
    if client is None:
        client = await run_in_threadpool(_get_storage_client)
    
    bucket = client.bucket(intake_cfg.intake_settings.GCS_BUCKET_NAME)
    blob = bucket.blob(storage_path)
    
    # generate_signed_url can be blocking if it needs to fetch keys
    return await run_in_threadpool(
        blob.generate_signed_url,
        version="v4",
        expiration=timedelta(hours=1),
        method="GET"
    )


async def ingest_single_file(
    current_user_id: str,
    file: UploadFile,
    processing_id: str,
    file_content: bytes,
    file_hash: str,
) -> tuple[UploadedImage, str]:
    """Persist to GCS and insert one UploadFile into MongoDB.

    Returns (UploadedImage document, signed GCS URL).
    """
    from src.intake.models import UploadedImage, ImageStatus
    filename = file.filename or "unnamed_document"
    mime_type = file.content_type or "application/octet-stream"

    width, height = await get_image_dimensions(file_content)

    url = await save_to_storage(file_content, filename, processing_id, current_user_id)

    doc = UploadedImage(
        processing_id=processing_id,
        user_id=current_user_id,
        original_filename=filename,
        storage_path=f"{current_user_id}/{processing_id}/{filename}",
        mime_type=mime_type,
        file_size=len(file_content),
        file_hash_sha256=file_hash,
        width=width,
        height=height,
        status=ImageStatus.RECEIVED,
    )
    await doc.insert()
    return doc, url



async def list_documents(
    *,
    user_id: str,
    skip: int = 0,
    limit: int = 20,
    status_filter: str | None = None,
) -> list[UploadedImage]:
    """Return paginated UploadedImage documents for the given user."""
    from src.intake.models import UploadedImage, ImageStatus
    from beanie import PydanticObjectId

    query_conditions = [UploadedImage.status != ImageStatus.REJECTED_DUPLICATE]

    if user_id != "MOCK_USER":
        try:
            oid = PydanticObjectId(user_id)
            query_conditions.append(UploadedImage.user_id == oid)
        except Exception:
            pass

    if status_filter:
        try:
            query_conditions.append(UploadedImage.status == ImageStatus(status_filter))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid status filter: '{status_filter}'",
            )

    docs = await UploadedImage.find(*query_conditions).sort(-UploadedImage.uploaded_at).skip(skip).limit(limit).to_list()

    if not docs:
        return []

    # Generate signed URLs for each document
    client = await run_in_threadpool(_get_storage_client)
    for doc in docs:
        try:
            doc.file_url = await _generate_signed_url(doc.storage_path, client=client)
        except Exception:
            pass

    return docs


async def get_image_urls(
    processing_id: str,
    user_id: str,
) -> list[str]:
    """Find all images for a processing_id and return their signed GCS URLs."""
    from src.intake.models import UploadedImage, ImageStatus
    from beanie import PydanticObjectId

    docs: list[UploadedImage] = []
    try:
        oid = PydanticObjectId(processing_id)
        doc = await UploadedImage.find_one(UploadedImage.id == oid)
        if doc:
            docs = [doc]
    except Exception:
        pass

    if not docs:
        docs = await UploadedImage.find(UploadedImage.processing_id == processing_id).to_list()

    # Filter out soft-deleted ones
    docs = [d for d in docs if d.status != ImageStatus.REJECTED_INVALID]

    if not docs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document(s) for '{processing_id}' not found",
        )

    if user_id != "MOCK_USER":
        try:
            user_oid = PydanticObjectId(user_id)
            for d in docs:
                if d.user_id != user_oid:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        except Exception as exc:
            if isinstance(exc, HTTPException):
                raise
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    client = await run_in_threadpool(_get_storage_client)
    urls: list[str] = []

    for doc in docs:
        try:
            url = await _generate_signed_url(doc.storage_path, client=client)
            urls.append(url)
        except Exception:
            pass

    return urls


async def get_image_stream(
    processing_id: str,
    user_id: str,
) -> tuple[Iterator[bytes], str, str]:
    """Fetch the original image from GCS and return (byte_iterator, content_type, filename)."""
    from src.intake.models import UploadedImage, ImageStatus
    from beanie import PydanticObjectId

    doc = None
    try:
        oid = PydanticObjectId(processing_id)
        doc = await UploadedImage.find_one(UploadedImage.id == oid)
    except Exception:
        pass

    if doc is None:
        doc = await UploadedImage.find_one(UploadedImage.processing_id == processing_id)

    if doc is None or doc.status == ImageStatus.REJECTED_INVALID:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{processing_id}' not found",
        )

    if user_id != "MOCK_USER":
        try:
            if doc.user_id != PydanticObjectId(user_id):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        except Exception:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    if global_cfg.gcs_credentials:
        client = storage.Client(credentials=global_cfg.gcs_credentials)
    else:
        client = storage.Client()

    bucket = client.bucket(intake_cfg.intake_settings.GCS_BUCKET_NAME)
    blob = bucket.blob(doc.storage_path)

    if not blob.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image file not found in storage",
        )

    CHUNK_SIZE = 256 * 1024
    def _iter_chunks() -> Iterator[bytes]:
        with blob.open("rb") as f:
            while chunk := f.read(CHUNK_SIZE):
                yield chunk

    return _iter_chunks(), doc.mime_type, doc.original_filename


async def hard_delete(processing_id: str, user_id: str) -> None:
    """Permanently delete the document(s) from DB and GCS across all modules."""
    from src.intake.models import UploadedImage
    from src.preprocess.models import PreprocessedImage
    from src.ocr.models import OcrResult, AiVisionResult, BusinessCardScan
    from src.mapping.models import MappedDocument
    from src.confidence.models import ConfidenceReport, ProcessingHistory
    from src.review.models import JsonReviewSession, FinalizedDocument
    from beanie import PydanticObjectId
    import asyncio

    # 1. Identify all documents and storage paths
    uploaded_images = await UploadedImage.find(UploadedImage.processing_id == processing_id).to_list()
    if not uploaded_images:
        # We still try to delete other related data just in case intake record was lost
        # but let's check if there's ANYTHING for this processing_id in other collections
        # to avoid 404 if the processing_id is totally invalid.
        if not await PreprocessedImage.find_one(PreprocessedImage.processing_id == processing_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document '{processing_id}' not found")

    # 2. Permission check (if not mock user)
    if user_id != "MOCK_USER":
        user_oid = PydanticObjectId(user_id)
        for doc in uploaded_images:
            if doc.user_id != user_oid:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    # 3. Determine GCS prefix for deletion
    gcs_prefixes: set[str] = set()
    
    # Prefix from UploadedImage
    for doc in uploaded_images:
        if doc.user_id:
            gcs_prefixes.add(f"{str(doc.user_id)}/{processing_id}/")
    
    # Prefix from PreprocessedImage (if any)
    preprocessed_images = await PreprocessedImage.find(PreprocessedImage.processing_id == processing_id).to_list()
    for p_img in preprocessed_images:
        if p_img.processed_storage_path:
            parts = p_img.processed_storage_path.split("/")
            if len(parts) >= 2:
                gcs_prefixes.add(f"{parts[0]}/{parts[1]}/")
                
    # Fallback if no docs found but we have a user_id
    if not gcs_prefixes and user_id != "MOCK_USER":
        gcs_prefixes.add(f"{user_id}/{processing_id}/")

    # 4. Delete from Database (All related collections)
    await asyncio.gather(
        UploadedImage.find(UploadedImage.processing_id == processing_id).delete(),
        PreprocessedImage.find(PreprocessedImage.processing_id == processing_id).delete(),
        OcrResult.find(OcrResult.processing_id == processing_id).delete(),
        AiVisionResult.find(AiVisionResult.processing_id == processing_id).delete(),
        BusinessCardScan.find(BusinessCardScan.processing_id == processing_id).delete(),
        MappedDocument.find(MappedDocument.processing_id == processing_id).delete(),
        ConfidenceReport.find(ConfidenceReport.processing_id == processing_id).delete(),
        ProcessingHistory.find(ProcessingHistory.processing_id == processing_id).delete(),
        JsonReviewSession.find(JsonReviewSession.processing_id == processing_id).delete(),
        FinalizedDocument.find(FinalizedDocument.processing_id == processing_id).delete(),
    )

    # 5. Delete from GCS (Folder level)
    if gcs_prefixes:
        client = await run_in_threadpool(_get_storage_client)
        bucket = client.bucket(intake_cfg.intake_settings.GCS_BUCKET_NAME)

        def _delete_folders(prefixes: set[str]):
            for prefix in prefixes:
                try:
                    # Convert iterator to list to ensure all blobs are captured and deleted
                    blobs = list(bucket.list_blobs(prefix=prefix))
                    if blobs:
                        bucket.delete_blobs(blobs)
                except Exception:
                    # Log or ignore errors during mass deletion
                    pass

        await run_in_threadpool(_delete_folders, gcs_prefixes)
