from datetime import datetime, timezone

from src.common.base_model import CustomModel


class FileEntry(CustomModel):
    """Metadata for one uploaded file within a submission."""

    original_filename: str
    file_url: str


class UploadResponse(CustomModel):
    """Response returned after a successful upload (1 or 2 files, 202 Accepted)."""

    processing_id: str
    files: list[FileEntry]
    status: str = "queued"
    uploaded_at: datetime = datetime.now(tz=timezone.utc)


class DocumentSummary(CustomModel):
    """Lightweight summary of one uploaded document, used in the list endpoint."""

    processing_id: str
    original_filename: str
    mime_type: str
    file_size: int
    status: str
    uploaded_at: datetime
    file_urls: list[str] = []


class DocumentListResponse(CustomModel):
    """Response containing a list of document summaries and pagination metadata."""

    items: list[DocumentSummary]
    total: int
    skip: int
    limit: int


class DeleteResponse(CustomModel):
    """Response returned after a successful document soft-delete."""

    processing_id: str
    status: str = "deleted"
