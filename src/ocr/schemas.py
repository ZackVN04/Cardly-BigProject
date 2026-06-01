from pydantic import BaseModel, Field


class BusinessCard(BaseModel):
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
    detected_languages: list[str] = Field(
        default_factory=list, 
        description="List of detected language codes (e.g., 'vi', 'en', 'other')"
    )


from typing import Optional, Any

class ExtractionResponse(BaseModel):
    name: Optional[str] = Field(None, description="The name of the person")
    phones: list[str] = Field(default_factory=list, description="The phone number of the person")
    email: Optional[str] = Field(None, description="The email address of the person")
    company: Optional[str] = Field(None, description="The company name of the person")
    position: Optional[str] = Field(None, description="The position of the person")
    address: Optional[str] = Field(None, description="The address of the person")
    website: Optional[str] = Field(None, description="The website of the person")
    social_profiles: list[str] = Field(
        default_factory=list,
        description="Social profile URLs found on the card (LinkedIn, Facebook, Zalo, etc.)",
    )
    detected_languages: list[str] = Field(
        default_factory=list, 
        description="List of detected language codes (e.g., 'vi', 'en', 'other')"
    )
    confidence_score: float = Field(0.0, description="Overall confidence score (0.0 to 1.0)")
    field_scores: list[Any] = Field(default_factory=list, description="Detailed scores for each field")
