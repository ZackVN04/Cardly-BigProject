from pydantic import BaseModel, Field
from typing import Optional

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
