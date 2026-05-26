from pydantic import BaseModel, Field


class BusinessCard(BaseModel):
    name: str = Field(description="The name of the person")
    phones: list[str] = Field(description="The phone number of the person")
    email: str = Field(description="The email address of the person")
    company: str = Field(description="The company name of the person")
    position: str = Field(description="The position of the person")
    address: str = Field(description="The address of the person")
    website: str = Field(description="The website of the person")
