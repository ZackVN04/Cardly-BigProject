from pydantic_settings import BaseSettings, SettingsConfigDict


class OcrConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    GEMINI_API_KEY: str = ""
    OCR_ENGINE: str = "gemini"   # "tesseract" | "gemini"
    MODEL_NAME: str = "gemini-1.5-pro"


ocr_settings = OcrConfig()
