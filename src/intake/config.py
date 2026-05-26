from pydantic_settings import BaseSettings, SettingsConfigDict


class IntakeConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    MAX_SIZE_MB: int = 10
    GCS_BUCKET_NAME: str = "cardly-images-bucket"
    ALLOWED_MIMES: list[str] = ["image/jpeg", "image/png", "image/webp"]


intake_settings = IntakeConfig()
