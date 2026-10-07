import asyncio
import json
import logging
from datetime import UTC, datetime
from uuid import uuid4

import anyio

from app.core.security import criar_token
from app.domain.entities.usuario import Usuario
from app.notifications.barramento import Assinatura, BarramentoNotificacoes
from app.notifications.websocket import atender_conexao
from tests.fixtures.fake_barramento_notificacoes import FakeBarramentoNotificacoes

_SEGREDO = "segredo"


class _SocketFalso:
    def __init__(self, primeira: dict):
        self._primeira = primeira
        self.enviadas: list[dict] = []
        self.autenticado = asyncio.Event()

    async def accept(self) -> None:
        return None

    async def receive(self) -> dict:
        if self._primeira is not None:
            mensagem, self._primeira = self._primeira, None
            return {"type": "websocket.receive", "text": json.dumps(mensagem)}
        await asyncio.Event().wait()

    async def send_json(self, dados: dict) -> None:
        self.enviadas.append(dados)
        if dados == {"tipo": "autenticado"}:
            self.autenticado.set()

    async def close(self, code: int = 1000) -> None:
        return None


def test_cancelamento_da_conexao_ainda_fecha_a_assinatura():
    usuario = Usuario.criar(
        id=uuid4(),
        nome="Ana",
        email="ana@example.com",
        senha="segredo123",
        criado_em=datetime.now(UTC),
    )
    barramento = FakeBarramentoNotificacoes()
    socket = _SocketFalso(
        {"tipo": "autenticar", "token": criar_token(usuario.id, _SEGREDO, expiracao_minutos=30)}
    )

    async def cenario():
        async with anyio.create_task_group() as grupo:
            grupo.start_soon(
                lambda: atender_conexao(
                    socket,
                    lambda _: usuario,
                    barramento,
                    jwt_secret_key=_SEGREDO,
                    timeout_autenticacao=1,
                    intervalo_ping=60,
                )
            )
            await socket.autenticado.wait()
            assert barramento.total_assinantes(usuario.id) == 1
            grupo.cancel_scope.cancel()

    anyio.run(cenario)

    assert barramento.total_assinantes(usuario.id) == 0


class _AssinaturaQueQuebra(Assinatura):
    def __init__(self) -> None:
        self.fechada = False

    async def proxima(self) -> dict:
        raise ConnectionError("redis caiu")

    async def fechar(self) -> None:
        self.fechada = True


class _BarramentoQueQuebra(BarramentoNotificacoes):
    def __init__(self) -> None:
        self.assinatura = _AssinaturaQueQuebra()

    def publicar(self, usuario_id, payload) -> None:
        return None

    async def assinar(self, usuario_id) -> Assinatura:
        return self.assinatura


def test_falha_do_barramento_durante_a_sessao_e_registrada_e_fecha_a_assinatura(caplog):
    usuario = Usuario.criar(
        id=uuid4(),
        nome="Ana",
        email="ana@example.com",
        senha="segredo123",
        criado_em=datetime.now(UTC),
    )
    barramento = _BarramentoQueQuebra()
    socket = _SocketFalso(
        {"tipo": "autenticar", "token": criar_token(usuario.id, _SEGREDO, expiracao_minutos=30)}
    )

    with caplog.at_level(logging.WARNING, logger="app.notifications.websocket"):
        anyio.run(
            lambda: atender_conexao(
                socket,
                lambda _: usuario,
                barramento,
                jwt_secret_key=_SEGREDO,
                timeout_autenticacao=1,
                intervalo_ping=60,
            )
        )

    assert barramento.assinatura.fechada is True
    assert any("redis caiu" in (r.exc_text or "") or r.exc_info for r in caplog.records)
