import os
from google.oauth2 import service_account
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.constants import Environment


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENVIRONMENT: Environment = Environment.LOCAL
    APP_VERSION: str = "1.0.0"

    MONGODB_URL: str
    REDIS_URL: str = "redis://localhost:6379/0"

    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    SENTRY_DSN: str | None = None

    GOOGLE_APPLICATION_CREDENTIALS: str | None = None

    @property
    def gcs_credentials(self) -> service_account.Credentials | None:
        if self.GOOGLE_APPLICATION_CREDENTIALS and os.path.exists(self.GOOGLE_APPLICATION_CREDENTIALS):
            return service_account.Credentials.from_service_account_file(self.GOOGLE_APPLICATION_CREDENTIALS)
        return None


settings = Config()
