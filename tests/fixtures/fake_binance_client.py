from __future__ import annotations

from app.domain.enums.periodo_historico import PeriodoHistorico
from app.integrations.binance.client import BinanceClient, BinanceIndisponivelError
from app.integrations.brapi.client import CotacaoAtual, PontoHistorico
from app.integrations.erros import TickerNaoEncontradoError


class FakeBinanceClient(BinanceClient):
    def __init__(
        self,
        pares: list[str] | None = None,
        cotacoes: dict[str, CotacaoAtual] | None = None,
        historicos: dict[str, list[PontoHistorico]] | None = None,
        indisponivel: bool = False,
    ):
        self._pares = pares if pares is not None else []
        self._cotacoes = cotacoes if cotacoes is not None else {}
        self._historicos = historicos if historicos is not None else {}
        self.indisponivel = indisponivel
        self.chamadas_catalogo = 0

    def listar_pares_brl(self) -> list[str]:
        self.chamadas_catalogo += 1
        if self.indisponivel:
            raise BinanceIndisponivelError
        return list(self._pares)

    def buscar_cotacao_atual(self, ticker: str) -> CotacaoAtual:
        if self.indisponivel:
            raise BinanceIndisponivelError
        if ticker not in self._cotacoes:
            raise TickerNaoEncontradoError(ticker)
        return self._cotacoes[ticker]

    def buscar_historico(self, ticker: str, periodo: PeriodoHistorico) -> list[PontoHistorico]:
        if self.indisponivel:
            raise BinanceIndisponivelError
        if ticker not in self._historicos:
            raise TickerNaoEncontradoError(ticker)
        return self._historicos[ticker]
