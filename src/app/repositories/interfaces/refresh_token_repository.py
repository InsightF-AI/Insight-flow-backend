from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from app.domain.entities.refresh_token import RefreshToken


class RefreshTokenRepository(ABC):
    @abstractmethod
    def salvar(self, token: RefreshToken) -> None: ...

    @abstractmethod
    def buscar_por_hash(self, token_hash: str) -> RefreshToken | None: ...

    @abstractmethod
    def revogar_se_ativo(self, token_id: UUID, revogado_em: datetime) -> bool: ...

    @abstractmethod
    def revogar_familia(self, familia_id: UUID, revogado_em: datetime) -> None: ...
