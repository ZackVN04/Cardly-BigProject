class EnrichmentResultDocument(BaseModel):
    id: Optional[str] = Field(default=None, alias="_id")
    contact_id: str
    professional_brief: Optional[str] = None
    keywords: list[str] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    generation_status: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)
