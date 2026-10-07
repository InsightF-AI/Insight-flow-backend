from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models.ticket_push import TicketPushModel
from app.domain.entities.ticket_push import TicketPush
from app.repositories.interfaces.ticket_push_repository import TicketPushRepository


class SqlAlchemyTicketPushRepository(TicketPushRepository):
    def __init__(self, session: Session):
        self._session = session

    def salvar_muitos(self, tickets: list[TicketPush]) -> None:
        for ticket in tickets:
            self._session.merge(
                TicketPushModel(id=ticket.id, token=ticket.token, criado_em=ticket.criado_em)
            )
        self._session.commit()

    def listar_anteriores_a(self, limite: datetime, quantidade: int) -> list[TicketPush]:
        modelos = self._session.scalars(
            select(TicketPushModel)
            .where(TicketPushModel.criado_em <= limite)
            .order_by(TicketPushModel.criado_em, TicketPushModel.id)
            .limit(quantidade)
        ).all()
        return [
            TicketPush(id=modelo.id, token=modelo.token, criado_em=modelo.criado_em)
            for modelo in modelos
        ]

    def remover_muitos(self, ids: list[str]) -> None:
        if not ids:
            return
        self._session.execute(delete(TicketPushModel).where(TicketPushModel.id.in_(ids)))
        self._session.commit()
