from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import httpx

from app.domain.enums.periodo_historico import PeriodoHistorico
from app.integrations.brapi.client import CotacaoAtual, PontoHistorico
from app.integrations.erros import FonteDadosIndisponivelError, TickerNaoEncontradoError

_MOEDA_COTACAO = "BRL"
_CODIGO_SIMBOLO_INVALIDO = -1121

_LIMITE_POR_PERIODO: dict[PeriodoHistorico, int] = {
    PeriodoHistorico.UM_DIA: 1,
    PeriodoHistorico.UMA_SEMANA: 7,
    PeriodoHistorico.UM_MES: 30,
    PeriodoHistorico.TRES_MESES: 90,
    PeriodoHistorico.UM_ANO: 365,
    PeriodoHistorico.CINCO_ANOS: 1000,
}


class BinanceIndisponivelError(FonteDadosIndisponivelError):
    pass


class BinanceClient:
    def __init__(self, http_client: httpx.Client):
        self._http_client = http_client

    def listar_pares_brl(self) -> list[str]:
        dados = self._get("/api/v3/exchangeInfo", {})
        return [
            simbolo["baseAsset"]
            for simbolo in dados.get("symbols", [])
            if simbolo.get("quoteAsset") == _MOEDA_COTACAO and simbolo.get("status") == "TRADING"
        ]

    def buscar_cotacao_atual(self, ticker: str) -> CotacaoAtual:
        dados = self._get("/api/v3/ticker/24hr", {"symbol": f"{ticker}{_MOEDA_COTACAO}"})
        return CotacaoAtual(
            ticker=ticker,
            preco=Decimal(dados["lastPrice"]),
            variacao=Decimal(dados["priceChange"]),
            variacao_percentual=Decimal(dados["priceChangePercent"]),
            maxima_dia=Decimal(dados["highPrice"]),
            minima_dia=Decimal(dados["lowPrice"]),
            volume=Decimal(dados["volume"]),
            abertura=Decimal(dados["openPrice"]),
        )

    def buscar_historico(self, ticker: str, periodo: PeriodoHistorico) -> list[PontoHistorico]:
        klines = self._get(
            "/api/v3/klines",
            {
                "symbol": f"{ticker}{_MOEDA_COTACAO}",
                "interval": "1d",
                "limit": str(_LIMITE_POR_PERIODO[periodo]),
            },
        )
        return [
            PontoHistorico(
                data=datetime.fromtimestamp(kline[0] / 1000, tz=UTC),
                abertura=Decimal(kline[1]),
                maxima=Decimal(kline[2]),
                minima=Decimal(kline[3]),
                fechamento=Decimal(kline[4]),
                volume=Decimal(kline[5]),
            )
            for kline in sorted(klines, key=lambda kline: kline[0])
        ]

    def _get(self, caminho: str, params: dict[str, str]):
        try:
            resposta = self._http_client.get(caminho, params=params)
            resposta.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 400 and (
                _codigo_erro(exc.response) == _CODIGO_SIMBOLO_INVALIDO
            ):
                raise TickerNaoEncontradoError(params.get("symbol")) from exc
            raise BinanceIndisponivelError from exc
        except httpx.HTTPError as exc:
            raise BinanceIndisponivelError from exc

        return resposta.json()


def _codigo_erro(resposta: httpx.Response) -> int | None:
    try:
        return resposta.json().get("code")
    except ValueError:
        return None
