from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfidenceConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    HIGH_THRESHOLD: float = 0.95
    LOW_THRESHOLD: float = 0.70


confidence_settings = ConfidenceConfig()
