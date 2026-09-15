from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.enums.tipo_ativo import TipoAtivo
from app.services.watchlist_service import ItemWatchlist


class AdicionarWatchlistRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=20)


class AtualizarNotificacaoRequest(BaseModel):
    notificar: bool


class AtivoResponse(BaseModel):
    id: UUID
    ticker: str
    nome: str
    tipo: TipoAtivo
    setor: str | None
    moeda: str


class ItemWatchlistResponse(BaseModel):
    ativo: AtivoResponse
    notificar: bool
    adicionado_em: datetime

    @staticmethod
    def de(item: ItemWatchlist) -> "ItemWatchlistResponse":
        return ItemWatchlistResponse(
            ativo=AtivoResponse(
                id=item.ativo.id,
                ticker=item.ativo.ticker,
                nome=item.ativo.nome,
                tipo=item.ativo.tipo,
                setor=item.ativo.setor,
                moeda=item.ativo.moeda,
            ),
            notificar=item.watchlist.notificar,
            adicionado_em=item.watchlist.adicionado_em,
        )
