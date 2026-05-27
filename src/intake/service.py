from __future__ import annotations

import io
from datetime import datetime, timedelta
from typing import Iterator, TYPE_CHECKING
from src.auth.dependencies import get_current_user

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



async def dedupe_by_hash(file_hash: str) -> None:
    """Raise 409 if a document with the same SHA-256 hash already exists in DB."""
    # Local import to avoid circular dependency with models.py
    from src.intake.models import UploadedImage, ImageStatus

    existing = await UploadedImage.find_one(
        UploadedImage.file_hash_sha256 == file_hash,
        UploadedImage.status != ImageStatus.REJECTED_DUPLICATE,
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Duplicate file detected (same SHA-256 hash)",
        )


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


def _generate_signed_url(storage_path: str, client: storage.Client | None = None) -> str:
    """Generate a signed URL for a given storage path.
    Client can be provided to reuse it in loops.
    """
    if client is None:
        client = _get_storage_client()
    bucket = client.bucket(intake_cfg.intake_settings.GCS_BUCKET_NAME)
    blob = bucket.blob(storage_path)
    return blob.generate_signed_url(version="v4", expiration=timedelta(hours=1), method="GET")


async def save_to_storage(file_content: bytes, filename: str, processing_id: str) -> str:
    """Upload the file bytes to Google Cloud Storage and return a signed URL."""
    client = _get_storage_client()
    storage_path = f"{processing_id}/{filename}"
    bucket = client.bucket(intake_cfg.intake_settings.GCS_BUCKET_NAME)
    blob = bucket.blob(storage_path)
    blob.upload_from_string(file_content)

    return _generate_signed_url(storage_path, client=client)


async def enqueue_pipeline_task(processing_id: str) -> None:
    """Push a pipeline task to the ARQ/Redis queue."""
    try:
        import arq
        redis = await arq.create_pool(arq.connections.RedisSettings.from_dsn(global_cfg.REDIS_URL))
        await redis.enqueue_job("process_document", processing_id)
        await redis.aclose()
    except Exception as exc:
        print(f"[intake] enqueue_pipeline_task skipped ({exc!r}) — processing_id={processing_id}")


async def ingest_single_file(current_user_id: str,
    file: UploadFile,
    processing_id: str,
) -> tuple[UploadedImage, str]:
    """Validate, persist to GCS, and insert one UploadFile into MongoDB.

    Returns (UploadedImage document, signed GCS URL).
    Both files in a multi-upload share the same ``processing_id`` and are
    stored under the same ``{processing_id}/`` folder in GCS.
    """
    from src.intake.models import UploadedImage, ImageStatus
    filename = file.filename or "unnamed_document"
    mime_type = file.content_type or "application/octet-stream"

    content = await file.read()

    file_hash = utils.sha256_of_file(content)
    await dedupe_by_hash(file_hash)

    width, height = await get_image_dimensions(content)

    url = await save_to_storage(content, filename, processing_id)

    doc = UploadedImage(
        processing_id=processing_id,
        user_id=current_user_id,
        original_filename=filename,
        storage_path=f"{processing_id}/{filename}",
        mime_type=mime_type,
        file_size=len(content),
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
    client = _get_storage_client()
    for doc in docs:
        try:
            doc.file_url = _generate_signed_url(doc.storage_path, client=client)
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

    client = _get_storage_client()
    urls: list[str] = []

    for doc in docs:
        try:
            url = _generate_signed_url(doc.storage_path, client=client)
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


async def soft_delete(processing_id: str, user_id: str) -> None:
    """Mark the document(s) as soft-deleted (status → REJECTED_INVALID)."""
    from src.intake.models import UploadedImage, ImageStatus
    from beanie import PydanticObjectId

    docs = []
    try:
        oid = PydanticObjectId(processing_id)
        doc = await UploadedImage.find_one(UploadedImage.id == oid)
        if doc:
            docs = [doc]
    except Exception:
        pass

    if not docs:
        docs = await UploadedImage.find(UploadedImage.processing_id == processing_id).to_list()

    if not docs:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document '{processing_id}' not found")

    for doc in docs:
        if user_id != "MOCK_USER":
            try:
                if doc.user_id != PydanticObjectId(user_id):
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
            except Exception:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

        if doc.status == ImageStatus.REJECTED_INVALID:
            continue

        doc.status = ImageStatus.REJECTED_INVALID
        await doc.save()
