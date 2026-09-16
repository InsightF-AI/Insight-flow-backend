from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.notificacao import Notificacao


class NotificacaoRepository(ABC):
    @abstractmethod
    def salvar(self, notificacao: Notificacao) -> None: ...

    @abstractmethod
    def buscar_por_id(self, notificacao_id: UUID) -> Notificacao | None: ...

    @abstractmethod
    def listar_por_usuario(
        self, usuario_id: UUID, apenas_nao_lidas: bool = False
    ) -> list[Notificacao]: ...
