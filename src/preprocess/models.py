from datetime import datetime
from enum import Enum

from beanie import Document, Indexed, PydanticObjectId
from pydantic import Field


class PreprocessingStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"


class PreprocessedImage(Document):
    """Post-preprocessing artifact. Original image is preserved unchanged."""

    processing_id: Indexed(str)  # type: ignore[valid-type]
    source_image_id: PydanticObjectId
    processed_storage_path: str
    resolution_dpi: int
    rotation_applied: int = 0
    brightness_delta: float = 0.0
    contrast_delta: float = 0.0
    output_format: str = "png"
    preprocessing_status: PreprocessingStatus = PreprocessingStatus.PENDING
    steps_applied: list[str] = []
    error_message: str | None = None
    processed_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "preprocessed_images"
