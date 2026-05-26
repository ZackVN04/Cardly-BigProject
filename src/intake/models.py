from datetime import datetime
from enum import Enum
from typing import Optional

from beanie import Document, Indexed
from beanie import PydanticObjectId
from pydantic import Field


class ImageStatus(str, Enum):
    RECEIVED = "received"
    VALIDATED = "validated"
    REJECTED_INVALID = "rejected_invalid"
    REJECTED_DUPLICATE = "rejected_duplicate"
    PREPROCESSING = "preprocessing"
    PROCESSED = "processed"
    FAILED = "failed"


class UploadedImage(Document):
    """Raw uploaded image with validation metadata.
    `processing_id` is the canonical correlation key used by every downstream collection.
    """

    processing_id: Indexed(str)  # type: ignore[valid-type]
    user_id: Optional[PydanticObjectId] = None
    original_filename: str
    storage_path: str
    mime_type: str
    file_size: int
    file_hash_sha256: Indexed(str)  # type: ignore[valid-type]
    width: Optional[int] = None
    height: Optional[int] = None
    status: ImageStatus = ImageStatus.RECEIVED
    validation_errors: list[str] = []
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)

    # Non-persistent field for API responses (not saved to MongoDB)
    file_url: Optional[str] = Field(default=None, exclude=True)

    class Settings:
        name = "uploaded_images"
