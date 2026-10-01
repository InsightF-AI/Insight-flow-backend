import pytest

from app.ai.providers.fabrica import criar_provedor_llm
from app.ai.providers.gemini import GeminiProvider
from app.core.config import Settings
from app.services.exceptions import LLMIndisponivelError


def test_ia_desabilitada_levanta_indisponivel():
    with pytest.raises(LLMIndisponivelError):
        criar_provedor_llm(Settings(_env_file=None, gemini_api_key="chave"))


def test_sem_chave_levanta_indisponivel():
    with pytest.raises(LLMIndisponivelError):
        criar_provedor_llm(Settings(_env_file=None, ai_habilitada=True))


def test_provedor_nao_suportado_levanta_indisponivel():
    settings = Settings(
        _env_file=None, ai_habilitada=True, gemini_api_key="chave", ai_provider="ollama"
    )

    with pytest.raises(LLMIndisponivelError):
        criar_provedor_llm(settings)


def test_configurado_retorna_gemini_provider():
    settings = Settings(
        _env_file=None, ai_habilitada=True, gemini_api_key="chave", gemini_model="gemini-x"
    )

    provedor = criar_provedor_llm(settings)

    assert isinstance(provedor, GeminiProvider)
    assert provedor.modelo == "gemini-x"
    assert provedor.nome == "gemini"
