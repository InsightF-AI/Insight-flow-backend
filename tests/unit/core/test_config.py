from app.core.config import Settings
from app.domain.enums.periodo_historico import PeriodoHistorico
from app.services.exceptions import (
    ContextoInsuficienteError,
    LLMCotaExcedidaError,
    LLMIndisponivelError,
    RespostaViolaGuardrailError,
)


def test_settings_ia_vem_desabilitada_por_padrao():
    settings = Settings(_env_file=None)

    assert settings.ai_habilitada is False
    assert settings.ai_provider == "gemini"
    assert settings.gemini_api_key == ""
    assert settings.gemini_model == "gemini-2.5-flash"
    assert settings.gemini_base_url == "https://generativelanguage.googleapis.com"
    assert settings.gemini_timeout_segundos == 30
    assert settings.gemini_backoff_segundos == 2
    assert settings.gemini_intervalo_entre_chamadas_segundos == 6
    assert settings.resumo_diario_hora == 18
    assert settings.resumo_diario_minuto == 30
    assert settings.chat_max_mensagens == 20
    assert settings.chat_max_caracteres_mensagem == 2000
    assert settings.max_iteracoes_ferramentas == 4


def test_cota_excedida_guarda_retry_after():
    erro = LLMCotaExcedidaError(retry_after=7)

    assert erro.retry_after == 7
    assert LLMCotaExcedidaError().retry_after is None


def test_excecoes_de_ia_sao_distintas():
    assert not issubclass(LLMCotaExcedidaError, LLMIndisponivelError)
    assert issubclass(RespostaViolaGuardrailError, Exception)
    assert issubclass(ContextoInsuficienteError, Exception)


def test_politica_historico_usa_os_valores_configurados():
    settings = Settings(
        _env_file=None,
        historico_backfill_periodo=PeriodoHistorico.UM_MES,
        historico_backfill_periodo_cripto=PeriodoHistorico.UM_ANO,
        historico_minimo_cotacoes=30,
    )

    politica = settings.politica_historico()

    assert politica.periodo_backfill is PeriodoHistorico.UM_MES
    assert politica.periodo_backfill_cripto is PeriodoHistorico.UM_ANO
    assert politica.minimo_cotacoes == 30


def test_backfill_de_cripto_padrao_e_cinco_anos():
    assert Settings(_env_file=None).historico_backfill_periodo_cripto is PeriodoHistorico.CINCO_ANOS
