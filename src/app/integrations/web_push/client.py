from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from enum import Enum
from urllib.parse import urlsplit

import httpx

from app.integrations.limitador import LimitadorTaxa, LimiteTaxaExcedidoError
from app.integrations.retentativa import (
    POLITICA_PADRAO,
    PoliticaRetentativa,
    executar_com_retentativa,
    so_falha_de_conexao,
)
from app.integrations.web_push.cifragem import cifrar
from app.integrations.web_push.vapid import ChaveVapid

logger = logging.getLogger(__name__)


class ResultadoWebPush(str, Enum):
    ENTREGUE = "ENTREGUE"
    INSCRICAO_EXPIRADA = "INSCRICAO_EXPIRADA"
    RECUSADO = "RECUSADO"


class WebPushIndisponivelError(Exception):
    pass


class WebPushClient:
    def __init__(
        self,
        http_client: httpx.Client,
        chave: ChaveVapid,
        contato: str,
        ttl_segundos: int,
        limitador: LimitadorTaxa | None = None,
        politica: PoliticaRetentativa = POLITICA_PADRAO,
        dormir: Callable[[float], None] = time.sleep,
        agora: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self._http_client = http_client
        self._chave = chave
        self._contato = contato
        self._ttl_segundos = ttl_segundos
        self._limitador = limitador
        self._politica = politica
        self._dormir = dormir
        self._agora = agora

    def enviar(self, endpoint: str, p256dh: str, auth: str, payload: dict) -> ResultadoWebPush:
        corpo = cifrar(json.dumps(payload, ensure_ascii=False).encode(), p256dh, auth)
        headers = {
            "Content-Encoding": "aes128gcm",
            "Content-Type": "application/octet-stream",
            "TTL": str(self._ttl_segundos),
            "Urgency": "high",
            "Authorization": self._chave.cabecalho_authorization(
                endpoint, self._contato, self._agora()
            ),
        }
        host = urlsplit(endpoint).hostname

        def requisitar() -> httpx.Response:
            if self._limitador is not None:
                self._limitador.adquirir()
            return self._http_client.post(endpoint, content=corpo, headers=headers)

        try:
            resposta = executar_com_retentativa(
                requisitar,
                self._politica,
                f"web push {host}",
                self._dormir,
                retentar_falha_de_rede=so_falha_de_conexao,
            )
        except LimiteTaxaExcedidoError as exc:
            raise WebPushIndisponivelError("Limite de taxa do web push") from exc
        except httpx.HTTPError as exc:
            raise WebPushIndisponivelError(type(exc).__name__) from exc

        status = resposta.status_code
        if 200 <= status < 300:
            return ResultadoWebPush.ENTREGUE
        if status in (404, 410):
            return ResultadoWebPush.INSCRICAO_EXPIRADA
        if status == 429 or status >= 500:
            raise WebPushIndisponivelError(f"HTTP {status}")
        logger.log(
            logging.ERROR if status in (401, 403) else logging.WARNING,
            "Servico de web push recusou o envio.",
            extra={"evento": "push_web_recusado", "status": status, "host": host},
        )
        return ResultadoWebPush.RECUSADO
