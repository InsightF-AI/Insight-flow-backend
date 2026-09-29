from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.notificacao import Notificacao
from app.domain.enums.tipo_notificacao import TipoNotificacao


class NotificacaoRepository(ABC):
    @abstractmethod
    def salvar(self, notificacao: Notificacao) -> None: ...

    @abstractmethod
    def buscar_por_id(self, notificacao_id: UUID) -> Notificacao | None: ...

    @abstractmethod
    def listar_por_usuario(
        self, usuario_id: UUID, apenas_nao_lidas: bool = False
    ) -> list[Notificacao]: ...

    @abstractmethod
    def buscar_ultima_do_tipo(
        self, usuario_id: UUID, tipo: TipoNotificacao
    ) -> Notificacao | None: ...
