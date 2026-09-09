from __future__ import annotations

from uuid import UUID

from app.domain.entities.watchlist import Watchlist
from app.repositories.interfaces.watchlist_repository import WatchlistRepository


class FakeWatchlistRepository(WatchlistRepository):
    def __init__(self) -> None:
        self._itens: dict[UUID, Watchlist] = {}

    def salvar(self, watchlist: Watchlist) -> None:
        self._itens[watchlist.id] = watchlist

    def remover(self, watchlist: Watchlist) -> None:
        self._itens.pop(watchlist.id, None)

    def listar_por_usuario(self, usuario_id: UUID) -> list[Watchlist]:
        return [item for item in self._itens.values() if item.usuario_id == usuario_id]

    def buscar_por_usuario_e_ativo(self, usuario_id: UUID, ativo_id: UUID) -> Watchlist | None:
        for item in self._itens.values():
            if item.usuario_id == usuario_id and item.ativo_id == ativo_id:
                return item
        return None
