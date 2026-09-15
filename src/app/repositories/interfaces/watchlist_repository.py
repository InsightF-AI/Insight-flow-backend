from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.watchlist import Watchlist


class WatchlistRepository(ABC):
    @abstractmethod
    def salvar(self, watchlist: Watchlist) -> None: ...

    @abstractmethod
    def remover(self, watchlist: Watchlist) -> None: ...

    @abstractmethod
    def listar_por_usuario(self, usuario_id: UUID) -> list[Watchlist]: ...

    @abstractmethod
    def buscar_por_usuario_e_ativo(self, usuario_id: UUID, ativo_id: UUID) -> Watchlist | None: ...
