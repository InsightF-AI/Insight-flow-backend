from uuid import UUID

from pydantic import BaseModel

from app.domain.entities.ativo import Ativo
from app.domain.enums.tipo_ativo import TipoAtivo
from app.integrations.brapi.client import AtivoEncontrado


class AtivoEncontradoResponse(BaseModel):
    ticker: str
    nome: str
    tipo: TipoAtivo
    moeda: str
    setor: str | None

    @staticmethod
    def de(ativo: AtivoEncontrado) -> "AtivoEncontradoResponse":
        return AtivoEncontradoResponse(
            ticker=ativo.ticker,
            nome=ativo.nome,
            tipo=ativo.tipo,
            moeda=ativo.moeda,
            setor=ativo.setor,
        )


class AtivoCatalogoResponse(BaseModel):
    id: UUID
    ticker: str
    nome: str
    tipo: TipoAtivo
    setor: str | None
    moeda: str

    @staticmethod
    def de(ativo: Ativo) -> "AtivoCatalogoResponse":
        return AtivoCatalogoResponse(
            id=ativo.id,
            ticker=ativo.ticker,
            nome=ativo.nome,
            tipo=ativo.tipo,
            setor=ativo.setor,
            moeda=ativo.moeda,
        )
