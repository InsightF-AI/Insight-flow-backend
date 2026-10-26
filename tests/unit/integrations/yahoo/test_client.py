from datetime import date
from decimal import Decimal

import httpx
import pytest

from app.domain.value_objects.provento import Provento
from app.integrations.erros import TickerNaoEncontradoError
from app.integrations.retentativa import PoliticaRetentativa
from app.integrations.yahoo.client import YahooFinanceClient, YahooIndisponivelError


def _client(handler) -> YahooFinanceClient:
    http_client = httpx.Client(
        base_url="https://yahoo.test", transport=httpx.MockTransport(handler)
    )
    return YahooFinanceClient(
        http_client, politica=PoliticaRetentativa(tentativas=2), dormir=lambda _: None
    )


def _corpo(dividendos: dict) -> dict:
    return {"chart": {"result": [{"events": {"dividends": dividendos}}], "error": None}}


def test_busca_proventos_com_sufixo_da_b3_e_ordena_por_data_ex():
    capturado = {}

    def handler(request: httpx.Request) -> httpx.Response:
        capturado["path"] = request.url.path
        capturado["params"] = dict(request.url.params)
        return httpx.Response(
            200,
            json=_corpo(
                {
                    "1733144400": {"amount": 0.099922, "date": 1733144400},
                    "1730466000": {"amount": 0.08993, "date": 1730466000},
                }
            ),
        )

    proventos = _client(handler).buscar_proventos("MXRF11")

    assert capturado["path"] == "/v8/finance/chart/MXRF11.SA"
    assert capturado["params"] == {"range": "5y", "interval": "1mo", "events": "div"}
    assert proventos == [
        Provento(data_ex=date(2024, 11, 1), valor_por_cota=Decimal("0.08993")),
        Provento(data_ex=date(2024, 12, 2), valor_por_cota=Decimal("0.099922")),
    ]


def test_sem_eventos_retorna_lista_vazia():
    corpo = {"chart": {"result": [{"meta": {}}], "error": None}}

    assert _client(lambda _: httpx.Response(200, json=corpo)).buscar_proventos("BOVA11") == []


def test_404_vira_ticker_nao_encontrado():
    with pytest.raises(TickerNaoEncontradoError):
        _client(lambda _: httpx.Response(404, json={})).buscar_proventos("XXXX99")


def test_erro_persistente_vira_indisponivel():
    with pytest.raises(YahooIndisponivelError):
        _client(lambda _: httpx.Response(503)).buscar_proventos("PETR4")


def test_corpo_invalido_vira_indisponivel():
    with pytest.raises(YahooIndisponivelError):
        _client(lambda _: httpx.Response(200, content=b"<html>")).buscar_proventos("PETR4")
