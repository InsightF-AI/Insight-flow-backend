from __future__ import annotations

from functools import lru_cache

import anthropic
import httpx

from app.ai.providers.base import ProvedorLLM
from app.ai.providers.claude import ClaudeProvider
from app.ai.providers.gemini import GeminiProvider
from app.ai.providers.openai_compativel import OpenAICompativelProvider
from app.core.config import Settings
from app.services.exceptions import LLMIndisponivelError


@lru_cache
def _http_client(base_url: str, timeout_segundos: int) -> httpx.Client:
    return httpx.Client(base_url=base_url, timeout=timeout_segundos)


@lru_cache
def _cliente_anthropic(api_key: str, timeout_segundos: int, tentativas: int) -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=api_key, timeout=timeout_segundos, max_retries=tentativas)


def criar_provedor_llm(settings: Settings) -> ProvedorLLM:
    if settings.ai_provider not in ("claude", "gemini", "openai", "ollama"):
        raise LLMIndisponivelError(f"Provedor de IA nao suportado: {settings.ai_provider}")
    if not settings.ai_configurada():
        raise LLMIndisponivelError("Provedor de IA nao configurado")

    if settings.ai_provider == "claude":
        return ClaudeProvider(
            _cliente_anthropic(
                settings.anthropic_api_key,
                settings.anthropic_timeout_segundos,
                settings.anthropic_max_tentativas,
            ),
            settings.anthropic_model,
            settings.anthropic_esforco,
        )
    if settings.ai_provider == "gemini":
        return GeminiProvider(
            _http_client(settings.gemini_base_url, settings.gemini_timeout_segundos),
            settings.gemini_api_key,
            settings.gemini_model,
            settings.gemini_backoff_segundos,
        )
    if settings.ai_provider == "openai":
        return OpenAICompativelProvider(
            _http_client(settings.openai_base_url, settings.openai_compativel_timeout_segundos),
            "openai",
            settings.openai_model,
            settings.openai_api_key,
        )
    return OpenAICompativelProvider(
        _http_client(settings.ollama_base_url, settings.openai_compativel_timeout_segundos),
        "ollama",
        settings.ollama_model,
    )
