from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import httpx

from app.domain.enums.periodo_historico import PeriodoHistorico
from app.domain.enums.tipo_ativo import TipoAtivo

_MAPA_SUBTYPE: dict[str, TipoAtivo] = {
    "stock": TipoAtivo.ACAO,
    "fii": TipoAtivo.FII,
    "etf": TipoAtivo.ETF,
    "bdr": TipoAtivo.BDR,
}

_MAPA_PERIODO: dict[PeriodoHistorico, tuple[str, str]] = {
    PeriodoHistorico.UM_DIA: ("1d", "5m"),
    PeriodoHistorico.UMA_SEMANA: ("5d", "1d"),
    PeriodoHistorico.UM_MES: ("1mo", "1d"),
    PeriodoHistorico.TRES_MESES: ("3mo", "1d"),
    PeriodoHistorico.UM_ANO: ("1y", "1d"),
    PeriodoHistorico.CINCO_ANOS: ("5y", "1wk"),
}


class BrapiIndisponivelError(Exception):
    pass


class TickerNaoEncontradoError(Exception):
    pass


@dataclass
class AtivoEncontrado:
    ticker: str
    nome: str
    tipo: TipoAtivo
    moeda: str
    setor: str | None


@dataclass
class CotacaoAtual:
    ticker: str
    preco: Decimal
    variacao: Decimal
    variacao_percentual: Decimal
    maxima_dia: Decimal
    minima_dia: Decimal
    volume: Decimal


@dataclass
class PontoHistorico:
    data: datetime
    abertura: Decimal
    maxima: Decimal
    minima: Decimal
    fechamento: Decimal
    volume: Decimal


class BrapiClient:
    def __init__(self, http_client: httpx.Client, api_key: str | None = None):
        self._http_client = http_client
        self._api_key = api_key

    def buscar_ativos(self, termo: str) -> list[AtivoEncontrado]:
        dados = self._get("/api/v2/tickers", {"search": termo})

        resultado = []
        for item in dados.get("results", []):
            tipo = _MAPA_SUBTYPE.get(item.get("subType"))
            if tipo is None:
                continue
            resultado.append(
                AtivoEncontrado(
                    ticker=item["symbol"],
                    nome=item["name"],
                    tipo=tipo,
                    moeda=item["currency"],
                    setor=item.get("sector"),
                )
            )
        return resultado

    def buscar_cotacao_atual(self, ticker: str) -> CotacaoAtual:
        dados = self._get("/api/v2/stocks/quote", {"symbols": ticker})
        resultados = dados.get("results", [])
        if not resultados:
            raise TickerNaoEncontradoError(ticker)
        item = resultados[0]["data"]
        return CotacaoAtual(
            ticker=ticker,
            preco=Decimal(str(item["regularMarketPrice"])),
            variacao=Decimal(str(item["regularMarketChange"])),
            variacao_percentual=Decimal(str(item["regularMarketChangePercent"])),
            maxima_dia=Decimal(str(item["regularMarketDayHigh"])),
            minima_dia=Decimal(str(item["regularMarketDayLow"])),
            volume=Decimal(str(item["regularMarketVolume"])),
        )

    def buscar_historico(self, ticker: str, periodo: PeriodoHistorico) -> list[PontoHistorico]:
        intervalo_range, intervalo = _MAPA_PERIODO[periodo]
        dados = self._get(
            "/api/v2/stocks/historical",
            {"symbols": ticker, "range": intervalo_range, "interval": intervalo},
        )
        resultados = dados.get("results", [])
        if not resultados:
            raise TickerNaoEncontradoError(ticker)
        pontos = resultados[0]["data"].get("historicalDataPrice", [])
        return [
            PontoHistorico(
                data=datetime.fromtimestamp(ponto["date"], tz=UTC),
                abertura=Decimal(str(ponto["open"])),
                maxima=Decimal(str(ponto["high"])),
                minima=Decimal(str(ponto["low"])),
                fechamento=Decimal(str(ponto["close"])),
                volume=Decimal(str(ponto["volume"])),
            )
            for ponto in pontos
        ]

    def _get(self, caminho: str, params: dict[str, str]) -> dict:
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        try:
            resposta = self._http_client.get(caminho, params=params, headers=headers)
            resposta.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise TickerNaoEncontradoError from exc
            raise BrapiIndisponivelError from exc
        except httpx.HTTPError as exc:
            raise BrapiIndisponivelError from exc

        return resposta.json()
