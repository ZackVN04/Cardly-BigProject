# TODO(P2 — Phúc Khang): Implement intake schemas
from datetime import datetime

from src.common.base_model import CustomModel


class UploadResponse(CustomModel):
    processing_id: str
    status: str
    uploaded_at: datetime


class DocumentSummary(CustomModel):
    processing_id: str
    doc_type: str | None = None
    status: str
    uploaded_at: datetime
