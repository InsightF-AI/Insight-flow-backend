from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from app.domain.entities.ticket_push import TicketPush


class TicketPushRepository(ABC):
    @abstractmethod
    def salvar_muitos(self, tickets: list[TicketPush]) -> None: ...

    @abstractmethod
    def listar_anteriores_a(self, limite: datetime, quantidade: int) -> list[TicketPush]: ...

    @abstractmethod
    def remover_muitos(self, ids: list[str]) -> None: ...
