
from pydantic import BaseModel, Field


class BusinessCardFields(BaseModel):
    """Extracted and enriched fields from a business card.
    All fields are Optional so that partial extraction is valid.
    """
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    web: str | None = None
    position: str | None = None
    company: str | None = None

    # AI Enrichment (defaulted to None/empty for now, not implemented yet)
    industry: str | None = None
    summary: str | None = None
    keywords: list[str] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)
