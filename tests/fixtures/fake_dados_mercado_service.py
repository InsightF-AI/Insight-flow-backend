from __future__ import annotations

from app.domain.enums.periodo_historico import PeriodoHistorico
from app.integrations.brapi.client import (
    AtivoEncontrado,
    BrapiIndisponivelError,
    CotacaoAtual,
    PontoHistorico,
    TickerNaoEncontradoError,
)
from app.services.dados_mercado_service import DadosMercadoService


class FakeDadosMercadoService(DadosMercadoService):
    def __init__(
        self,
        catalogo: list[AtivoEncontrado] | None = None,
        cotacoes: dict[str, CotacaoAtual] | None = None,
        historicos: dict[str, list[PontoHistorico]] | None = None,
        indisponivel: bool = False,
    ):
        self._catalogo = catalogo if catalogo is not None else []
        self._cotacoes = cotacoes if cotacoes is not None else {}
        self._historicos = historicos if historicos is not None else {}
        self.indisponivel = indisponivel

    def buscar_ativo(self, termo: str) -> list[AtivoEncontrado]:
        if self.indisponivel:
            raise BrapiIndisponivelError

        termo_normalizado = termo.lower()
        return [
            ativo
            for ativo in self._catalogo
            if termo_normalizado in ativo.ticker.lower() or termo_normalizado in ativo.nome.lower()
        ]

    def buscar_cotacao_atual(self, ticker: str) -> CotacaoAtual:
        if self.indisponivel:
            raise BrapiIndisponivelError
        if ticker not in self._cotacoes:
            raise TickerNaoEncontradoError(ticker)
        return self._cotacoes[ticker]

    def buscar_historico(self, ticker: str, periodo: PeriodoHistorico) -> list[PontoHistorico]:
        if self.indisponivel:
            raise BrapiIndisponivelError
        if ticker not in self._historicos:
            raise TickerNaoEncontradoError(ticker)
        return self._historicos[ticker]
