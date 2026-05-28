from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    JWT_SECRET: str = "change-me-in-prod"
    JWT_ALG: str = "HS256"
    JWT_EXP: int = 15            # access token lifetime in minutes
    REFRESH_TOKEN_EXP: int = 7   # refresh token lifetime in days

    OTP_EXP_MINUTES: int = 10    # OTP validity window

    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = ""
    EMAIL_FROM_NAME: str = "Cardly"


auth_settings = AuthConfig()
