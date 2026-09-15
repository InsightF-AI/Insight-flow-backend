from __future__ import annotations

from uuid import UUID

from app.domain.entities.indicador_tecnico import IndicadorTecnico
from app.repositories.interfaces.indicador_tecnico_repository import IndicadorTecnicoRepository


class FakeIndicadorTecnicoRepository(IndicadorTecnicoRepository):
    def __init__(self) -> None:
        self._indicadores: dict[tuple, IndicadorTecnico] = {}

    def salvar(self, indicador: IndicadorTecnico) -> None:
        chave = (indicador.ativo_id, indicador.tipo, tuple(sorted(indicador.parametros.items())))
        self._indicadores[chave] = indicador

    def salvar_muitas(self, indicadores: list[IndicadorTecnico]) -> None:
        for indicador in indicadores:
            self.salvar(indicador)

    def listar_por_ativo(self, ativo_id: UUID) -> list[IndicadorTecnico]:
        return [i for i in self._indicadores.values() if i.ativo_id == ativo_id]
