from functools import lru_cache

import httpx

from app.core.config import Settings
from app.integrations.expo.client import ExpoPushClient
from app.integrations.limitadores import limitador_compartilhado


@lru_cache
def _http_client(base_url: str) -> httpx.Client:
    return httpx.Client(base_url=base_url, timeout=10.0)


def criar_expo_client(settings: Settings) -> ExpoPushClient:
    return ExpoPushClient(
        _http_client(settings.expo_base_url),
        access_token=settings.expo_access_token or None,
        limitador=limitador_compartilhado(
            "expo",
            settings.expo_requisicoes_por_minuto,
            settings.integracoes_espera_maxima_segundos,
        ),
        politica=settings.politica_retentativa(),
    )
