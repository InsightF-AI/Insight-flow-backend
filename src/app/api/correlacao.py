from __future__ import annotations

import logging
import time

from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logs import em_correlacao, id_de_correlacao_valido

logger = logging.getLogger(__name__)

_HEADER = "x-request-id"
_CAMINHOS_SILENCIOSOS = {"/health"}
_CHAVE_USUARIO = "usuario_id_log"
_CORPO_ERRO_INTERNO = b'{"detail":"Internal Server Error"}'


def registrar_usuario_na_requisicao(request: Request, usuario_id: object) -> None:
    setattr(request.state, _CHAVE_USUARIO, str(usuario_id))


def _id_recebido(scope: Scope) -> str | None:
    for nome, valor in scope.get("headers", []):
        if nome.decode("latin-1").lower() == _HEADER:
            texto = valor.decode("latin-1")
            return texto if id_de_correlacao_valido(texto) else None
    return None


class CorrelacaoMiddleware:
    def __init__(self, app: ASGIApp):
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self._app(scope, receive, send)
            return

        with em_correlacao(_id_recebido(scope)) as correlation_id:
            if scope["type"] == "websocket":
                await self._app(scope, receive, send)
                return
            await self._atender_http(scope, receive, send, correlation_id)

    async def _atender_http(
        self, scope: Scope, receive: Receive, send: Send, correlation_id: str
    ) -> None:
        inicio = time.perf_counter()
        status = 500
        iniciada = False

        async def enviar(mensagem: Message) -> None:
            nonlocal status, iniciada
            if mensagem["type"] == "http.response.start":
                status = mensagem["status"]
                iniciada = True
                mensagem["headers"] = [
                    *mensagem.get("headers", []),
                    (_HEADER.encode("latin-1"), correlation_id.encode("latin-1")),
                ]
            await send(mensagem)

        try:
            await self._app(scope, receive, enviar)
        except Exception:
            _logar_requisicao(scope, 500, inicio, erro=True)
            if iniciada:
                raise
            await enviar(
                {
                    "type": "http.response.start",
                    "status": 500,
                    "headers": [(b"content-type", b"application/json")],
                }
            )
            await enviar({"type": "http.response.body", "body": _CORPO_ERRO_INTERNO})
            return
        _logar_requisicao(scope, status, inicio)


def _logar_requisicao(scope: Scope, status: int, inicio: float, erro: bool = False) -> None:
    caminho = scope.get("path", "")
    if caminho in _CAMINHOS_SILENCIOSOS:
        return
    estado = scope.get("state") or {}
    logger.log(
        logging.ERROR if status >= 500 else logging.INFO,
        "Requisicao %s %s respondida com %d.",
        scope.get("method"),
        caminho,
        status,
        exc_info=erro,
        extra={
            "metodo": scope.get("method"),
            "caminho": caminho,
            "status": status,
            "duracao_ms": round((time.perf_counter() - inicio) * 1000, 1),
            "usuario_id": estado.get(_CHAVE_USUARIO),
        },
    )
