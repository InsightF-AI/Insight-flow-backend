from __future__ import annotations

from uuid import UUID

from app.domain.entities.sinal import Sinal
from app.repositories.interfaces.sinal_repository import SinalRepository


class FakeSinalRepository(SinalRepository):
    def __init__(self) -> None:
        self._sinais: dict[UUID, Sinal] = {}

    def salvar(self, sinal: Sinal) -> None:
        self._sinais[sinal.id] = sinal

    def buscar_ativo(self, ativo_id: UUID, regra_id: UUID) -> Sinal | None:
        for sinal in self._sinais.values():
            if (
                sinal.ativo_id == ativo_id
                and sinal.regra_id == regra_id
                and sinal.data_desativacao is None
            ):
                return sinal
        return None

    def listar_por_ativo(self, ativo_id: UUID) -> list[Sinal]:
        return [sinal for sinal in self._sinais.values() if sinal.ativo_id == ativo_id]
