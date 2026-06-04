from __future__ import annotations

from pydantic import BaseModel, Field


class ExtractionError(BaseModel):
    code: str
    message: str


class ExtractionResponse(BaseModel):
    name: str | None = None
    phones: list[str] = Field(default_factory=list)
    email: str | None = None
    company: str | None = None
    position: str | None = None
    address: str | None = None
    website: str | None = None
    social_profiles: list[str] = Field(default_factory=list)
    field_confidences: dict[str, float] = Field(default_factory=dict)
    raw_text: str | None = None
    extraction_status: str = "completed"
    errors: list[ExtractionError] = Field(default_factory=list)
