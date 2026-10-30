from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.ativo import Ativo
from app.domain.enums.tipo_ativo import TipoAtivo


class AtivoRepository(ABC):
    @abstractmethod
    def salvar(self, ativo: Ativo) -> None: ...

    @abstractmethod
    def buscar_por_id(self, id: UUID) -> Ativo | None: ...

    @abstractmethod
    def buscar_por_ticker(self, ticker: str) -> Ativo | None: ...

    @abstractmethod
    def listar(self, tipo: TipoAtivo | None = None) -> list[Ativo]: ...
