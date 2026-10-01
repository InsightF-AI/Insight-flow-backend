from __future__ import annotations

from functools import lru_cache

import httpx

from app.ai.providers.base import ProvedorLLM
from app.ai.providers.gemini import GeminiProvider
from app.core.config import Settings
from app.services.exceptions import LLMIndisponivelError


@lru_cache
def _http_client_gemini(base_url: str, timeout_segundos: int) -> httpx.Client:
    return httpx.Client(base_url=base_url, timeout=timeout_segundos)


def criar_provedor_llm(settings: Settings) -> ProvedorLLM:
    if not settings.ai_habilitada or not settings.gemini_api_key:
        raise LLMIndisponivelError("Provedor de IA nao configurado")
    if settings.ai_provider != "gemini":
        raise LLMIndisponivelError(f"Provedor de IA nao suportado: {settings.ai_provider}")
    return GeminiProvider(
        _http_client_gemini(settings.gemini_base_url, settings.gemini_timeout_segundos),
        settings.gemini_api_key,
        settings.gemini_model,
        settings.gemini_backoff_segundos,
    )
