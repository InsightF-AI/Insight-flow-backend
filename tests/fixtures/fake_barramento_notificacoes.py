from __future__ import annotations

import asyncio
import threading
from uuid import UUID

from app.notifications.barramento import Assinatura, BarramentoNotificacoes


class _AssinaturaFake(Assinatura):
    def __init__(self, barramento: FakeBarramentoNotificacoes, usuario_id: UUID):
        self._barramento = barramento
        self._usuario_id = usuario_id
        self._loop = asyncio.get_running_loop()
        self._fila: asyncio.Queue = asyncio.Queue()

    def _receber(self, payload: dict) -> None:
        self._loop.call_soon_threadsafe(self._fila.put_nowait, payload)

    async def proxima(self) -> dict:
        return await self._fila.get()

    async def fechar(self) -> None:
        self._barramento._remover(self._usuario_id, self)


class FakeBarramentoNotificacoes(BarramentoNotificacoes):
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._assinaturas: dict[UUID, list[_AssinaturaFake]] = {}
        self.publicados: list[tuple[UUID, dict]] = []
        self.falhar = False

    def publicar(self, usuario_id: UUID, payload: dict) -> None:
        if self.falhar:
            raise ConnectionError("barramento fora do ar")
        self.publicados.append((usuario_id, payload))
        with self._lock:
            alvos = list(self._assinaturas.get(usuario_id, []))
        for assinatura in alvos:
            assinatura._receber(payload)

    async def assinar(self, usuario_id: UUID) -> Assinatura:
        assinatura = _AssinaturaFake(self, usuario_id)
        with self._lock:
            self._assinaturas.setdefault(usuario_id, []).append(assinatura)
        return assinatura

    def total_assinantes(self, usuario_id: UUID) -> int:
        with self._lock:
            return len(self._assinaturas.get(usuario_id, []))

    def _remover(self, usuario_id: UUID, assinatura: _AssinaturaFake) -> None:
        with self._lock:
            if assinatura in self._assinaturas.get(usuario_id, []):
                self._assinaturas[usuario_id].remove(assinatura)
