from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

import httpx

from app.domain.value_objects.provento import Provento
from app.integrations.erros import FonteDadosIndisponivelError, TickerNaoEncontradoError
from app.integrations.limitador import LimitadorTaxa, LimiteTaxaExcedidoError
from app.integrations.retentativa import (
    POLITICA_PADRAO,
    PoliticaRetentativa,
    executar_com_retentativa,
)

USER_AGENT = "Mozilla/5.0 (compatible; InsightFlow/1.0)"
_SUFIXO_B3 = ".SA"
_JANELA = "5y"


class YahooIndisponivelError(FonteDadosIndisponivelError):
    pass


class YahooFinanceClient:
    def __init__(
        self,
        http_client: httpx.Client,
        limitador: LimitadorTaxa | None = None,
        politica: PoliticaRetentativa = POLITICA_PADRAO,
        dormir: Callable[[float], None] = time.sleep,
    ):
        self._http_client = http_client
        self._limitador = limitador
        self._politica = politica
        self._dormir = dormir

    def buscar_proventos(self, ticker: str) -> list[Provento]:
        caminho = f"/v8/finance/chart/{ticker}{_SUFIXO_B3}"
        params = {"range": _JANELA, "interval": "1mo", "events": "div"}

        def requisitar() -> httpx.Response:
            if self._limitador is not None:
                self._limitador.adquirir()
            return self._http_client.get(caminho, params=params)

        try:
            resposta = executar_com_retentativa(
                requisitar, self._politica, f"yahoo {caminho}", self._dormir
            )
            resposta.raise_for_status()
            dados = resposta.json()
        except LimiteTaxaExcedidoError as exc:
            raise YahooIndisponivelError from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise TickerNaoEncontradoError(ticker) from exc
            raise YahooIndisponivelError from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise YahooIndisponivelError from exc

        resultados = (dados.get("chart") or {}).get("result") or []
        if not resultados:
            raise TickerNaoEncontradoError(ticker)
        dividendos = (resultados[0].get("events") or {}).get("dividends") or {}
        proventos = [
            Provento(
                data_ex=datetime.fromtimestamp(item["date"], tz=UTC).date(),
                valor_por_cota=Decimal(str(item["amount"])),
            )
            for item in dividendos.values()
        ]
        return sorted(proventos, key=lambda provento: provento.data_ex)
