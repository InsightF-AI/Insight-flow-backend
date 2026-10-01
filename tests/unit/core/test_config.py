from app.core.config import Settings
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
