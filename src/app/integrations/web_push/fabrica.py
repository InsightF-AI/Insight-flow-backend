from functools import lru_cache

import httpx

from app.core.config import Settings
from app.integrations.limitadores import limitador_compartilhado
from app.integrations.web_push.client import WebPushClient
from app.integrations.web_push.vapid import ChaveVapid


@lru_cache
def _http_client() -> httpx.Client:
    return httpx.Client(timeout=10.0, follow_redirects=False)


def criar_web_push_client(settings: Settings) -> WebPushClient | None:
    if not settings.web_push_configurado():
        return None
    return WebPushClient(
        _http_client(),
        ChaveVapid.de_base64url(settings.web_push_vapid_chave_privada),
        settings.web_push_vapid_contato,
        settings.web_push_ttl_segundos,
        limitador=limitador_compartilhado(
            "web_push",
            settings.web_push_requisicoes_por_minuto,
            settings.integracoes_espera_maxima_segundos,
        ),
        politica=settings.politica_retentativa(),
    )
