from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.inscricao_web_push import InscricaoWebPush


class InscricaoWebPushRepository(ABC):
    @abstractmethod
    def buscar_por_endpoint(self, endpoint: str) -> InscricaoWebPush | None: ...

    @abstractmethod
    def salvar(self, inscricao: InscricaoWebPush) -> None: ...

    @abstractmethod
    def listar_por_usuario(self, usuario_id: UUID) -> list[InscricaoWebPush]: ...

    @abstractmethod
    def remover_por_endpoint(self, endpoint: str) -> None: ...
