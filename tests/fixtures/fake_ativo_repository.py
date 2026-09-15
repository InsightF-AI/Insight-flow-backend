from __future__ import annotations

from uuid import UUID

from app.domain.entities.ativo import Ativo
from app.repositories.interfaces.ativo_repository import AtivoRepository


class FakeAtivoRepository(AtivoRepository):
    def __init__(self) -> None:
        self._ativos: dict[UUID, Ativo] = {}

    def salvar(self, ativo: Ativo) -> None:
        self._ativos[ativo.id] = ativo

    def buscar_por_id(self, id: UUID) -> Ativo | None:
        return self._ativos.get(id)

    def buscar_por_ticker(self, ticker: str) -> Ativo | None:
        for ativo in self._ativos.values():
            if ativo.ticker == ticker:
                return ativo
        return None
