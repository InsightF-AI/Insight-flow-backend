import pytest

from app.ai.providers.claude import ClaudeProvider
from app.ai.providers.fabrica import criar_provedor_llm
from app.ai.providers.gemini import GeminiProvider
from app.ai.providers.openai_compativel import OpenAICompativelProvider
from app.core.config import Settings
from app.services.exceptions import LLMIndisponivelError


def test_ia_desabilitada_levanta_indisponivel():
    with pytest.raises(LLMIndisponivelError):
        criar_provedor_llm(Settings(_env_file=None, anthropic_api_key="chave"))


def test_sem_chave_levanta_indisponivel():
    with pytest.raises(LLMIndisponivelError):
        criar_provedor_llm(Settings(_env_file=None, ai_habilitada=True))


def test_provedor_nao_suportado_levanta_indisponivel():
    settings = Settings(
        _env_file=None, ai_habilitada=True, anthropic_api_key="chave", ai_provider="mistral"
    )

    with pytest.raises(LLMIndisponivelError):
        criar_provedor_llm(settings)


def test_padrao_retorna_claude_haiku():
    provedor = criar_provedor_llm(
        Settings(_env_file=None, ai_habilitada=True, anthropic_api_key="chave")
    )

    assert isinstance(provedor, ClaudeProvider)
    assert provedor.nome == "claude"
    assert provedor.modelo == "claude-haiku-5-5"


def test_gemini_configurado_retorna_gemini_provider():
    settings = Settings(
        _env_file=None,
        ai_habilitada=True,
        ai_provider="gemini",
        gemini_api_key="chave",
        gemini_model="gemini-x",
    )

    provedor = criar_provedor_llm(settings)

    assert isinstance(provedor, GeminiProvider)
    assert provedor.modelo == "gemini-x"


def test_openai_e_ollama_usam_o_adaptador_compativel():
    openai = criar_provedor_llm(
        Settings(
            _env_file=None,
            ai_habilitada=True,
            ai_provider="openai",
            openai_api_key="chave",
            openai_model="gpt-x",
        )
    )
    ollama = criar_provedor_llm(
        Settings(_env_file=None, ai_habilitada=True, ai_provider="ollama", ollama_model="llama")
    )

    assert isinstance(openai, OpenAICompativelProvider)
    assert (openai.nome, openai.modelo) == ("openai", "gpt-x")
    assert isinstance(ollama, OpenAICompativelProvider)
    assert (ollama.nome, ollama.modelo) == ("ollama", "llama")
