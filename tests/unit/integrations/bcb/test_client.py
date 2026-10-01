from datetime import date
from decimal import Decimal

import httpx
import pytest

from app.integrations.bcb.client import BcbClient, BcbIndisponivelError, PontoCdi


def _client(handler) -> BcbClient:
    transporte = httpx.MockTransport(handler)
    http_client = httpx.Client(base_url="https://api.bcb.gov.br", transport=transporte)
    return BcbClient(http_client)


def test_buscar_ptax_venda_mapeia_o_valor_mais_recente():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/dados/serie/bcdata.sgs.1/dados/ultimos/1"
        assert request.url.params["formato"] == "json"
        return httpx.Response(200, json=[{"data": "12/09/2025", "valor": "5.4321"}])

    client = _client(handler)

    taxa = client.buscar_ptax_venda()

    assert taxa == Decimal("5.4321")


def test_buscar_ptax_venda_com_lista_vazia_lanca_bcb_indisponivel():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    client = _client(handler)

    with pytest.raises(BcbIndisponivelError):
        client.buscar_ptax_venda()


def test_buscar_ptax_venda_com_erro_http_lanca_bcb_indisponivel():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"message": "erro interno"})

    client = _client(handler)

    with pytest.raises(BcbIndisponivelError):
        client.buscar_ptax_venda()


def test_buscar_ptax_venda_com_erro_de_rede_lanca_bcb_indisponivel():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("conexao recusada", request=request)

    client = _client(handler)

    with pytest.raises(BcbIndisponivelError):
        client.buscar_ptax_venda()


def test_buscar_serie_cdi_mapeia_pontos_diarios():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/dados/serie/bcdata.sgs.12/dados"
        assert request.url.params["dataInicial"] == "01/09/2026"
        assert request.url.params["dataFinal"] == "10/09/2026"
        return httpx.Response(
            200,
            json=[
                {"data": "01/09/2026", "valor": "0.051660"},
                {"data": "02/09/2026", "valor": "0.051660"},
            ],
        )

    client = _client(handler)

    pontos = client.buscar_serie_cdi(date(2026, 9, 1), date(2026, 9, 10))

    assert pontos == [
        PontoCdi(data=date(2026, 9, 1), valor=Decimal("0.051660")),
        PontoCdi(data=date(2026, 9, 2), valor=Decimal("0.051660")),
    ]


def test_buscar_serie_cdi_com_erro_http_lanca_bcb_indisponivel():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"message": "erro interno"})

    client = _client(handler)

    with pytest.raises(BcbIndisponivelError):
        client.buscar_serie_cdi(date(2026, 9, 1), date(2026, 9, 10))
