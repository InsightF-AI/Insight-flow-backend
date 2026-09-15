from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.cotacao import Cotacao


class CotacaoRepository(ABC):
    @abstractmethod
    def salvar_muitas(self, cotacoes: list[Cotacao]) -> None: ...

    @abstractmethod
    def listar_por_ativo(self, ativo_id: UUID) -> list[Cotacao]: ...
