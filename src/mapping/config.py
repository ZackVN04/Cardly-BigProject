from pydantic_settings import BaseSettings, SettingsConfigDict


class MappingConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    MAPPER_VERSION: str = "1.0.0"


mapping_settings = MappingConfig()
