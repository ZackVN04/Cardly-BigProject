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

    GOOGLE_SERVICE_ACCOUNT_JSON: dict | None = None

    @property
    def gcs_credentials(self) -> service_account.Credentials | None:
        if self.GOOGLE_SERVICE_ACCOUNT_JSON:
            return service_account.Credentials.from_service_account_info(self.GOOGLE_SERVICE_ACCOUNT_JSON)
        return None


settings = Config()
