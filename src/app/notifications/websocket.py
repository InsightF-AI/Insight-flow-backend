from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

import anyio
from fastapi import WebSocket, WebSocketDisconnect

from app.core.security import TokenInvalidoError, decodificar_token_com_expiracao
from app.domain.entities.usuario import Usuario
from app.notifications.barramento import Assinatura, BarramentoNotificacoes

CODIGO_NAO_AUTENTICADO = 4401
CODIGO_ERRO_INTERNO = 1011

logger = logging.getLogger(__name__)


async def _receber_json(websocket: WebSocket):
    mensagem = await websocket.receive()
    if mensagem["type"] == "websocket.disconnect":
        raise WebSocketDisconnect(mensagem.get("code", 1000))
    texto = mensagem.get("text")
    if texto is None:
        raise ValueError("mensagem nao e texto")
    return json.loads(texto)


async def _fechar(websocket: WebSocket, codigo: int) -> None:
    with contextlib.suppress(Exception):
        await websocket.close(code=codigo)


class _Sessao:
    def __init__(self, usuario_id: UUID, expira_em: datetime):
        self.usuario_id = usuario_id
        self.expira_em = expira_em


async def _validar(
    mensagem, buscar_usuario: Callable[[UUID], Usuario | None], jwt_secret_key: str
) -> tuple[UUID, datetime] | None:
    if not isinstance(mensagem, dict) or mensagem.get("tipo") != "autenticar":
        return None
    try:
        usuario_id, expira_em = decodificar_token_com_expiracao(
            str(mensagem.get("token", "")), jwt_secret_key
        )
    except TokenInvalidoError:
        return None
    usuario = await asyncio.to_thread(buscar_usuario, usuario_id)
    if usuario is None or not usuario.ativo:
        return None
    return usuario_id, expira_em


async def _repassar(websocket: WebSocket, assinatura: Assinatura) -> bool:
    while True:
        await websocket.send_json(await assinatura.proxima())


async def _pingar(websocket: WebSocket, intervalo: float) -> bool:
    while True:
        await asyncio.sleep(intervalo)
        await websocket.send_json({"tipo": "ping"})


async def _ler(
    websocket: WebSocket,
    sessao: _Sessao,
    buscar_usuario: Callable[[UUID], Usuario | None],
    jwt_secret_key: str,
) -> bool:
    while True:
        try:
            mensagem = await _receber_json(websocket)
        except WebSocketDisconnect:
            return False
        except ValueError:
            continue
        if not isinstance(mensagem, dict) or mensagem.get("tipo") != "autenticar":
            continue
        validado = await _validar(mensagem, buscar_usuario, jwt_secret_key)
        if validado is None or validado[0] != sessao.usuario_id:
            return True
        sessao.expira_em = validado[1]
        await websocket.send_json({"tipo": "autenticado"})


async def _vigiar_expiracao(sessao: _Sessao) -> bool:
    while True:
        restante = (sessao.expira_em - datetime.now(UTC)).total_seconds()
        if restante <= 0:
            return True
        await asyncio.sleep(min(restante, 1.0))


async def atender_conexao(
    websocket: WebSocket,
    buscar_usuario: Callable[[UUID], Usuario | None],
    barramento: BarramentoNotificacoes,
    jwt_secret_key: str,
    timeout_autenticacao: float,
    intervalo_ping: float,
) -> None:
    await websocket.accept()
    try:
        primeira = await asyncio.wait_for(_receber_json(websocket), timeout_autenticacao)
    except WebSocketDisconnect:
        return
    except (TimeoutError, ValueError):
        await _fechar(websocket, CODIGO_NAO_AUTENTICADO)
        return

    validado = await _validar(primeira, buscar_usuario, jwt_secret_key)
    if validado is None:
        await _fechar(websocket, CODIGO_NAO_AUTENTICADO)
        return

    sessao = _Sessao(*validado)
    assinatura = await barramento.assinar(sessao.usuario_id)
    tarefas: list[asyncio.Task] = []
    try:
        await websocket.send_json({"tipo": "autenticado"})
        tarefas = [
            asyncio.create_task(_repassar(websocket, assinatura)),
            asyncio.create_task(_pingar(websocket, intervalo_ping)),
            asyncio.create_task(_ler(websocket, sessao, buscar_usuario, jwt_secret_key)),
            asyncio.create_task(_vigiar_expiracao(sessao)),
        ]
        concluidas, _ = await asyncio.wait(tarefas, return_when=asyncio.FIRST_COMPLETED)
        tarefa = next(iter(concluidas))
        erro = None if tarefa.cancelled() else tarefa.exception()
        if erro is not None:
            logger.warning(
                "Conexao de notificacoes do usuario %s encerrada por erro.",
                sessao.usuario_id,
                exc_info=erro,
            )
            await _fechar(websocket, CODIGO_ERRO_INTERNO)
        elif not tarefa.cancelled() and tarefa.result() is True:
            await _fechar(websocket, CODIGO_NAO_AUTENTICADO)
    finally:
        with anyio.CancelScope(shield=True):
            for tarefa in tarefas:
                tarefa.cancel()
            await asyncio.gather(*tarefas, return_exceptions=True)
            await assinatura.fechar()
