from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://insightflow:insightflow@localhost:5432/insightflow"

    jwt_secret_key: str = "dev-secret-key-nao-usar-em-producao"
    jwt_expiration_minutes: int = 1440


@lru_cache
def get_settings() -> Settings:
    return Settings()
