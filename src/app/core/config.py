from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://insightflow:insightflow@localhost:5432/insightflow"

    jwt_secret_key: str = "dev-secret-key-nao-usar-em-producao"
    jwt_expiration_minutes: int = 1440

    brapi_base_url: str = "https://brapi.dev"
    brapi_api_key: str = ""

    redis_url: str = "redis://localhost:6381/0"
    cache_ttl_cotacao_atual_segundos: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()
