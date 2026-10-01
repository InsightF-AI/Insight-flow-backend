from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.analise_ia import AnaliseIA


class AnaliseIARepository(ABC):
    @abstractmethod
    def salvar(self, analise: AnaliseIA) -> None: ...

    @abstractmethod
    def buscar_ultima_por_ativo(self, ativo_id: UUID) -> AnaliseIA | None: ...
