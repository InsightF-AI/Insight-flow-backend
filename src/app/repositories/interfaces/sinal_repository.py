from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.sinal import Sinal


class SinalRepository(ABC):
    @abstractmethod
    def salvar(self, sinal: Sinal) -> None: ...

    @abstractmethod
    def buscar_ativo(self, ativo_id: UUID, regra_id: UUID) -> Sinal | None: ...

    @abstractmethod
    def listar_por_ativo(self, ativo_id: UUID) -> list[Sinal]: ...
