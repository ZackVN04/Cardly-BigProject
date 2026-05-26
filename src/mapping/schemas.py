from typing import Optional
from pydantic import BaseModel, Field

class BusinessCardFields(BaseModel):
    """Extracted and enriched fields from a business card.
    All fields are Optional so that partial extraction is valid.
    """
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    web: Optional[str] = None
    position: Optional[str] = None
    company: Optional[str] = None

    # AI Enrichment (defaulted to None/empty for now, not implemented yet)
    industry: Optional[str] = None
    summary: Optional[str] = None
    keywords: list[str] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)
