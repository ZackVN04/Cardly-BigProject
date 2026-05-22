from pydantic_settings import BaseSettings, SettingsConfigDict


class PreprocessConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    MIN_DPI: int = 300
    MAX_DIMENSION: int = 4096
    OUTPUT_FORMAT: str = "png"


preprocess_settings = PreprocessConfig()
