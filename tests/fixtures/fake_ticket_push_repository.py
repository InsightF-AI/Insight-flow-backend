from __future__ import annotations

from datetime import datetime

from app.domain.entities.ticket_push import TicketPush
from app.repositories.interfaces.ticket_push_repository import TicketPushRepository


class FakeTicketPushRepository(TicketPushRepository):
    def __init__(self) -> None:
        self._tickets: dict[str, TicketPush] = {}

    def salvar_muitos(self, tickets: list[TicketPush]) -> None:
        for ticket in tickets:
            self._tickets[ticket.id] = ticket

    def listar_anteriores_a(self, limite: datetime, quantidade: int) -> list[TicketPush]:
        elegiveis = sorted(
            (t for t in self._tickets.values() if t.criado_em <= limite),
            key=lambda t: (t.criado_em, t.id),
        )
        return elegiveis[:quantidade]

    def remover_muitos(self, ids: list[str]) -> None:
        for id_ in ids:
            self._tickets.pop(id_, None)

    def listar_todos(self) -> list[TicketPush]:
        return list(self._tickets.values())
