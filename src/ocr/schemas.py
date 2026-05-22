from pydantic import BaseModel


class OcrBlockSchema(BaseModel):
    text: str
    bbox: list[float]
    confidence: float


class VisionRegionSchema(BaseModel):
    label: str
    bbox: list[float]
    confidence: float
