from pydantic_settings import BaseSettings, SettingsConfigDict


class IntakeConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    MAX_SIZE_MB: int = 10
    STORAGE_PATH: str = "/tmp/ocr_uploads"
    ALLOWED_MIMES: list[str] = ["image/jpeg", "image/png", "image/webp", "application/pdf"]


intake_settings = IntakeConfig()
