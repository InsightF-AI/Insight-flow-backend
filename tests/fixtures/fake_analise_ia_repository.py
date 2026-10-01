from __future__ import annotations

from uuid import UUID

from app.domain.entities.analise_ia import AnaliseIA
from app.repositories.interfaces.analise_ia_repository import AnaliseIARepository


class FakeAnaliseIARepository(AnaliseIARepository):
    def __init__(self) -> None:
        self._analises: dict[UUID, AnaliseIA] = {}

    def salvar(self, analise: AnaliseIA) -> None:
        self._analises[analise.id] = analise

    def buscar_ultima_por_ativo(self, ativo_id: UUID) -> AnaliseIA | None:
        analises = [a for a in self._analises.values() if a.ativo_id == ativo_id]
        if not analises:
            return None
        return max(analises, key=lambda a: a.gerado_em)

    def listar_todas(self) -> list[AnaliseIA]:
        return list(self._analises.values())
