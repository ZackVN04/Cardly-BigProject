from pydantic_settings import BaseSettings, SettingsConfigDict


class ReviewConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    SESSION_TIMEOUT_HOURS: int = 24


review_settings = ReviewConfig()
