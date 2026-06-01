from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from src.enrichment.constants import GenerationStatus


class EnrichmentResultBase(BaseModel):
    professional_brief: Optional[str] = None
    keywords: Optional[list[str]] = None
    highlights: Optional[list[str]] = None


class EnrichmentRequest(BaseModel):
    name: str = Field(description="The name of the person")
    phones: list[str] = Field(description="The phone number of the person")
    email: str = Field(description="The email address of the person")
    company: str = Field(description="The company name of the person")
    position: str = Field(description="The position of the person")
    address: str = Field(description="The address of the person")
    website: str = Field(description="The website of the person")
    social_profiles: list[str] = Field(
        default_factory=list,
        description="Social profile URLs found on the card (LinkedIn, Facebook, Zalo, etc.)",
    )


class EnrichmentResponse(EnrichmentResultBase):
    generation_status: GenerationStatus
