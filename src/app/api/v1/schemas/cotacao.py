from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.integrations.brapi.client import CotacaoAtual, PontoHistorico


class CotacaoAtualResponse(BaseModel):
    ticker: str
    preco: Decimal
    variacao: Decimal
    variacao_percentual: Decimal
    maxima_dia: Decimal
    minima_dia: Decimal
    volume: Decimal

    @staticmethod
    def de(cotacao: CotacaoAtual) -> "CotacaoAtualResponse":
        return CotacaoAtualResponse(
            ticker=cotacao.ticker,
            preco=cotacao.preco,
            variacao=cotacao.variacao,
            variacao_percentual=cotacao.variacao_percentual,
            maxima_dia=cotacao.maxima_dia,
            minima_dia=cotacao.minima_dia,
            volume=cotacao.volume,
        )


class PontoHistoricoResponse(BaseModel):
    data: datetime
    abertura: Decimal
    maxima: Decimal
    minima: Decimal
    fechamento: Decimal
    volume: Decimal

    @staticmethod
    def de(ponto: PontoHistorico) -> "PontoHistoricoResponse":
        return PontoHistoricoResponse(
            data=ponto.data,
            abertura=ponto.abertura,
            maxima=ponto.maxima,
            minima=ponto.minima,
            fechamento=ponto.fechamento,
            volume=ponto.volume,
        )
