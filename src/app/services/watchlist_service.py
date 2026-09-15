from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domain.entities.ativo import Ativo
from app.domain.entities.watchlist import Watchlist
from app.repositories.interfaces.ativo_repository import AtivoRepository
from app.repositories.interfaces.watchlist_repository import WatchlistRepository
from app.services.dados_mercado_service import DadosMercadoService
from app.services.exceptions import (
    AtivoJaNaWatchlistError,
    AtivoNaoEncontradoError,
    ItemWatchlistNaoEncontradoError,
)


@dataclass
class ItemWatchlist:
    ativo: Ativo
    watchlist: Watchlist


class WatchlistService:
    def __init__(
        self,
        watchlist_repository: WatchlistRepository,
        ativo_repository: AtivoRepository,
        dados_mercado_service: DadosMercadoService,
    ):
        self._watchlist_repository = watchlist_repository
        self._ativo_repository = ativo_repository
        self._dados_mercado_service = dados_mercado_service

    def adicionar(self, usuario_id: UUID, ticker: str) -> ItemWatchlist:
        ticker = ticker.upper()
        ativo = self._ativo_repository.buscar_por_ticker(ticker)
        if ativo is None:
            ativo = self._resolver_ativo_na_brapi(ticker)
            self._ativo_repository.salvar(ativo)

        if self._watchlist_repository.buscar_por_usuario_e_ativo(usuario_id, ativo.id) is not None:
            raise AtivoJaNaWatchlistError(ticker)

        item = Watchlist.adicionar(
            id=uuid4(), usuario_id=usuario_id, ativo_id=ativo.id, adicionado_em=datetime.now(UTC)
        )
        self._watchlist_repository.salvar(item)
        return ItemWatchlist(ativo=ativo, watchlist=item)

    def remover(self, usuario_id: UUID, ativo_id: UUID) -> None:
        item = self._buscar_item(usuario_id, ativo_id)
        self._watchlist_repository.remover(item)

    def listar(self, usuario_id: UUID) -> list[ItemWatchlist]:
        itens = self._watchlist_repository.listar_por_usuario(usuario_id)
        return [
            ItemWatchlist(ativo=self._ativo_repository.buscar_por_id(item.ativo_id), watchlist=item)
            for item in itens
        ]

    def definir_notificacao(
        self, usuario_id: UUID, ativo_id: UUID, notificar: bool
    ) -> ItemWatchlist:
        item = self._buscar_item(usuario_id, ativo_id)
        if notificar:
            item.habilitar_notificacao()
        else:
            item.desabilitar_notificacao()
        self._watchlist_repository.salvar(item)
        return ItemWatchlist(
            ativo=self._ativo_repository.buscar_por_id(item.ativo_id), watchlist=item
        )

    def _buscar_item(self, usuario_id: UUID, ativo_id: UUID) -> Watchlist:
        item = self._watchlist_repository.buscar_por_usuario_e_ativo(usuario_id, ativo_id)
        if item is None:
            raise ItemWatchlistNaoEncontradoError(ativo_id)
        return item

    def _resolver_ativo_na_brapi(self, ticker: str) -> Ativo:
        encontrados = self._dados_mercado_service.buscar_ativo(ticker)
        correspondente = next((a for a in encontrados if a.ticker == ticker), None)
        if correspondente is None:
            raise AtivoNaoEncontradoError(ticker)

        return Ativo(
            id=uuid4(),
            ticker=correspondente.ticker,
            nome=correspondente.nome,
            tipo=correspondente.tipo,
            setor=correspondente.setor,
            moeda=correspondente.moeda,
            fonte_dados="brapi",
        )
