from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.domain.enums.periodo_historico import PeriodoHistorico
from app.domain.value_objects.politica_historico import PoliticaHistorico


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://insightflow:insightflow@localhost:5432/insightflow"

    jwt_secret_key: str = "dev-secret-key-nao-usar-em-producao"
    jwt_expiration_minutes: int = 30
    refresh_token_expiracao_dias: int = 30

    cors_origens: list[str] = ["http://localhost:5173"]

    brapi_base_url: str = "https://brapi.dev"
    brapi_api_key: str = ""
    binance_base_url: str = "https://api.binance.com"

    redis_url: str = "redis://localhost:6381/0"
    cache_ttl_cotacao_atual_segundos: int = 60
    cache_ttl_historico_segundos: int = 86400
    cache_ttl_catalogo_cripto_segundos: int = 86400
    ws_timeout_autenticacao_segundos: float = 10
    ws_intervalo_ping_segundos: float = 30

    historico_backfill_periodo: PeriodoHistorico = PeriodoHistorico.TRES_MESES
    historico_backfill_periodo_cripto: PeriodoHistorico = PeriodoHistorico.CINCO_ANOS
    historico_minimo_cotacoes: int = 50
    indices_referencia_hora: int = 19
    indices_referencia_minuto: int = 0

    bcb_base_url: str = "https://api.bcb.gov.br"
    cache_ttl_cambio_segundos: int = 21600
    cache_ttl_cambio_fallback_segundos: int = 2592000

    scheduler_habilitado: bool = True
    scheduler_intervalo_renda_variavel_minutos: int = 15
    scheduler_intervalo_cripto_minutos: int = 5

    ai_habilitada: bool = False
    ai_provider: str = "gemini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_base_url: str = "https://generativelanguage.googleapis.com"
    gemini_timeout_segundos: int = 30
    gemini_backoff_segundos: int = 2
    gemini_intervalo_entre_chamadas_segundos: int = 6
    resumo_diario_hora: int = 18
    resumo_diario_minuto: int = 30
    chat_max_mensagens: int = 20
    chat_max_caracteres_mensagem: int = 2000
    max_iteracoes_ferramentas: int = 4

    def politica_historico(self) -> PoliticaHistorico:
        return PoliticaHistorico(
            periodo_backfill=self.historico_backfill_periodo,
            periodo_backfill_cripto=self.historico_backfill_periodo_cripto,
            minimo_cotacoes=self.historico_minimo_cotacoes,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
