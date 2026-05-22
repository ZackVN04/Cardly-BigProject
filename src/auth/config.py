# TODO(P1 — TBD): Implement auth config
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    JWT_SECRET: str = "change-me-in-prod"
    JWT_ALG: str = "HS256"
    JWT_EXP: int = 15           # minutes
    REFRESH_TOKEN_EXP: int = 30  # days


auth_settings = AuthConfig()
