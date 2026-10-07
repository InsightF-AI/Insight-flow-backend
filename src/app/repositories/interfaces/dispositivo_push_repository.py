from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from app.domain.entities.dispositivo_push import DispositivoPush


class DispositivoPushRepository(ABC):
    @abstractmethod
    def buscar_por_token(self, token: str) -> DispositivoPush | None: ...

    @abstractmethod
    def salvar(self, dispositivo: DispositivoPush) -> None: ...

    @abstractmethod
    def listar_ativos_por_usuario(self, usuario_id: UUID) -> list[DispositivoPush]: ...

    @abstractmethod
    def desativar_por_token(self, token: str, agora: datetime) -> None: ...
