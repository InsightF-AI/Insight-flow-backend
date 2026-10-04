from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID


class Assinatura(ABC):
    @abstractmethod
    async def proxima(self) -> dict: ...

    @abstractmethod
    async def fechar(self) -> None: ...


class BarramentoNotificacoes(ABC):
    @abstractmethod
    def publicar(self, usuario_id: UUID, payload: dict) -> None: ...

    @abstractmethod
    async def assinar(self, usuario_id: UUID) -> Assinatura: ...
