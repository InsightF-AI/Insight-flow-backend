from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.watchlist import WatchlistModel
from app.domain.entities.watchlist import Watchlist
from app.repositories.interfaces.watchlist_repository import WatchlistRepository


class SqlAlchemyWatchlistRepository(WatchlistRepository):
    def __init__(self, session: Session):
        self._session = session

    def salvar(self, watchlist: Watchlist) -> None:
        modelo = self._session.get(WatchlistModel, watchlist.id)
        if modelo is None:
            modelo = WatchlistModel(id=watchlist.id)
            self._session.add(modelo)

        modelo.usuario_id = watchlist.usuario_id
        modelo.ativo_id = watchlist.ativo_id
        modelo.adicionado_em = watchlist.adicionado_em
        modelo.notificar = watchlist.notificar
        self._session.commit()

    def remover(self, watchlist: Watchlist) -> None:
        modelo = self._session.get(WatchlistModel, watchlist.id)
        if modelo is not None:
            self._session.delete(modelo)
            self._session.commit()

    def listar_por_usuario(self, usuario_id: UUID) -> list[Watchlist]:
        modelos = self._session.scalars(
            select(WatchlistModel).where(WatchlistModel.usuario_id == usuario_id)
        )
        return [self._para_entidade(modelo) for modelo in modelos]

    def buscar_por_usuario_e_ativo(self, usuario_id: UUID, ativo_id: UUID) -> Watchlist | None:
        modelo = self._session.scalar(
            select(WatchlistModel).where(
                WatchlistModel.usuario_id == usuario_id,
                WatchlistModel.ativo_id == ativo_id,
            )
        )
        return self._para_entidade(modelo) if modelo is not None else None

    @staticmethod
    def _para_entidade(modelo: WatchlistModel) -> Watchlist:
        return Watchlist(
            id=modelo.id,
            usuario_id=modelo.usuario_id,
            ativo_id=modelo.ativo_id,
            adicionado_em=modelo.adicionado_em,
            notificar=modelo.notificar,
        )
