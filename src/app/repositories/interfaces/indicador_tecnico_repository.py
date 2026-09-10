from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.indicador_tecnico import IndicadorTecnico


class IndicadorTecnicoRepository(ABC):
    @abstractmethod
    def salvar(self, indicador: IndicadorTecnico) -> None: ...

    @abstractmethod
    def listar_por_ativo(self, ativo_id: UUID) -> list[IndicadorTecnico]: ...
