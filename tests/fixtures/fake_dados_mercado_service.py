from __future__ import annotations

from app.domain.enums.periodo_historico import PeriodoHistorico
from app.integrations.brapi.client import (
    INTERVALO_DIARIO,
    AtivoEncontrado,
    BrapiIndisponivelError,
    CotacaoAtual,
    PontoHistorico,
    intervalo_de,
)
from app.integrations.erros import TickerNaoEncontradoError
from app.services.dados_mercado_service import DadosMercadoService


class FakeDadosMercadoService(DadosMercadoService):
    def __init__(
        self,
        catalogo: list[AtivoEncontrado] | None = None,
        cotacoes: dict[str, CotacaoAtual] | None = None,
        historicos: dict[str, list[PontoHistorico]] | None = None,
        indisponivel: bool = False,
        tickers_diarios: set[str] | None = None,
        historicos_por_periodo: dict[tuple[str, PeriodoHistorico], list[PontoHistorico]]
        | None = None,
    ):
        self._catalogo = catalogo if catalogo is not None else []
        self._cotacoes = cotacoes if cotacoes is not None else {}
        self._historicos = historicos if historicos is not None else {}
        self.indisponivel = indisponivel
        self.erro_indisponivel: type[Exception] = BrapiIndisponivelError
        self._tickers_diarios = tickers_diarios or set()
        self._historicos_por_periodo = historicos_por_periodo or {}
        self.historicos_solicitados: list[tuple[str, PeriodoHistorico]] = []

    def buscar_ativo(self, termo: str) -> list[AtivoEncontrado]:
        if self.indisponivel:
            raise self.erro_indisponivel

        termo_normalizado = termo.lower()
        return [
            ativo
            for ativo in self._catalogo
            if termo_normalizado in ativo.ticker.lower() or termo_normalizado in ativo.nome.lower()
        ]

    def buscar_cotacao_atual(self, ticker: str) -> CotacaoAtual:
        if self.indisponivel:
            raise self.erro_indisponivel
        if ticker not in self._cotacoes:
            raise TickerNaoEncontradoError(ticker)
        return self._cotacoes[ticker]

    def buscar_historico(self, ticker: str, periodo: PeriodoHistorico) -> list[PontoHistorico]:
        self.historicos_solicitados.append((ticker, periodo))
        if self.indisponivel:
            raise self.erro_indisponivel
        if (ticker, periodo) in self._historicos_por_periodo:
            return self._historicos_por_periodo[(ticker, periodo)]
        if ticker not in self._historicos:
            raise TickerNaoEncontradoError(ticker)
        return self._historicos[ticker]

    def historico_e_diario(self, ticker: str, periodo: PeriodoHistorico) -> bool:
        return ticker in self._tickers_diarios or intervalo_de(periodo) == INTERVALO_DIARIO
