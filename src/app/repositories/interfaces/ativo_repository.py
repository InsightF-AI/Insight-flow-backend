from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.ativo import Ativo


class AtivoRepository(ABC):
    @abstractmethod
    def salvar(self, ativo: Ativo) -> None: ...

    @abstractmethod
    def buscar_por_id(self, id: UUID) -> Ativo | None: ...

    @abstractmethod
    def buscar_por_ticker(self, ticker: str) -> Ativo | None: ...
