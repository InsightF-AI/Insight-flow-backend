from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.operacao import Operacao


class OperacaoRepository(ABC):
    @abstractmethod
    def salvar(self, operacao: Operacao) -> None: ...

    @abstractmethod
    def buscar_por_id(self, operacao_id: UUID) -> Operacao | None: ...

    @abstractmethod
    def listar_por_usuario(self, usuario_id: UUID) -> list[Operacao]: ...

    @abstractmethod
    def remover(self, operacao: Operacao) -> None: ...
