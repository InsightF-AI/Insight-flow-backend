from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.domain.enums.periodo_historico import PeriodoHistorico
from app.domain.value_objects.politica_historico import PoliticaHistorico
from app.integrations.retentativa import PoliticaRetentativa
from app.integrations.web_push.validacao import HOSTS_PERMITIDOS_PADRAO
from app.integrations.web_push.vapid import ChaveVapid


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://insightflow:insightflow@localhost:5432/insightflow"

    jwt_secret_key: str = "dev-secret-key-nao-usar-em-producao"
    jwt_expiration_minutes: int = 30
    refresh_token_expiracao_dias: int = 30

    cors_origens: list[str] = ["http://localhost:5173"]
    log_nivel: str = "INFO"
    log_formato: str = "json"

    brapi_base_url: str = "https://brapi.dev"
    brapi_api_key: str = ""
    binance_base_url: str = "https://api.binance.com"
    brapi_requisicoes_por_minuto: int = 60
    binance_requisicoes_por_minuto: int = 600
    integracoes_tentativas: int = 3
    integracoes_backoff_base_segundos: float = 0.5
    integracoes_espera_maxima_segundos: float = 10.0
    expo_push_habilitado: bool = True
    expo_base_url: str = "https://exp.host"
    expo_access_token: str = ""
    expo_requisicoes_por_minuto: int = 300
    expo_recibos_intervalo_minutos: int = 30
    web_push_habilitado: bool = True
    web_push_vapid_chave_privada: str = ""
    web_push_vapid_contato: str = ""
    web_push_hosts_permitidos: list[str] = HOSTS_PERMITIDOS_PADRAO
    web_push_requisicoes_por_minuto: int = 300
    web_push_ttl_segundos: int = 86400

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
    ai_provider: str = "claude"
    ai_intervalo_entre_chamadas_segundos: int = 0
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-5-5"
    anthropic_esforco: str = "medium"
    anthropic_timeout_segundos: int = 60
    anthropic_max_tentativas: int = 2
    openai_api_key: str = ""
    openai_model: str = ""
    openai_base_url: str = "https://api.openai.com"
    ollama_model: str = ""
    ollama_base_url: str = "http://localhost:11434"
    openai_compativel_timeout_segundos: int = 60
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash"
    gemini_base_url: str = "https://generativelanguage.googleapis.com"
    gemini_timeout_segundos: int = 30
    gemini_backoff_segundos: int = 2
    gemini_intervalo_entre_chamadas_segundos: int = 6
    resumo_diario_hora: int = 18
    resumo_diario_minuto: int = 30
    chat_max_mensagens: int = 20
    chat_max_caracteres_mensagem: int = 2000
    max_iteracoes_ferramentas: int = 4

    def ai_configurada(self) -> bool:
        if not self.ai_habilitada:
            return False
        credenciais = {
            "claude": self.anthropic_api_key,
            "gemini": self.gemini_api_key,
            "openai": self.openai_api_key and self.openai_model,
            "ollama": self.ollama_model,
        }
        return bool(credenciais.get(self.ai_provider))

    def intervalo_entre_chamadas_ia(self) -> int:
        if self.ai_provider == "gemini":
            return self.gemini_intervalo_entre_chamadas_segundos
        return self.ai_intervalo_entre_chamadas_segundos

    def web_push_configurado(self) -> bool:
        if not (
            self.web_push_habilitado
            and self.web_push_vapid_chave_privada
            and self.web_push_vapid_contato.startswith(("mailto:", "https://"))
        ):
            return False
        try:
            ChaveVapid.de_base64url(self.web_push_vapid_chave_privada)
        except ValueError:
            return False
        return True

    def politica_retentativa(self) -> PoliticaRetentativa:
        return PoliticaRetentativa(
            tentativas=self.integracoes_tentativas,
            backoff_base_segundos=self.integracoes_backoff_base_segundos,
            espera_maxima_segundos=self.integracoes_espera_maxima_segundos,
        )

    def politica_historico(self) -> PoliticaHistorico:
        return PoliticaHistorico(
            periodo_backfill=self.historico_backfill_periodo,
            periodo_backfill_cripto=self.historico_backfill_periodo_cripto,
            minimo_cotacoes=self.historico_minimo_cotacoes,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
