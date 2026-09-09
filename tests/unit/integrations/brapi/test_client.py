import httpx
import pytest

from app.domain.enums.periodo_historico import PeriodoHistorico
from app.domain.enums.tipo_ativo import TipoAtivo
from app.integrations.brapi.client import (
    BrapiClient,
    BrapiIndisponivelError,
    TickerNaoEncontradoError,
)


def _client(handler, api_key: str | None = None) -> BrapiClient:
    transporte = httpx.MockTransport(handler)
    http_client = httpx.Client(base_url="https://brapi.dev", transport=transporte)
    return BrapiClient(http_client, api_key=api_key)


def test_buscar_ativos_mapeia_resultados_da_brapi():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["search"] == "petr"
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "symbol": "PETR4",
                        "name": "PETROBRAS PN",
                        "longName": "Petroleo Brasileiro S.A.",
                        "assetType": "stock",
                        "subType": "stock",
                        "exchange": "SAO",
                        "currency": "BRL",
                        "sector": "Petroleo e Gas",
                        "subsector": "Exploracao e Refino",
                        "isActive": True,
                        "logoUrl": "https://example.com/petr4.png",
                        "quote": 36.65,
                    }
                ],
                "indexes": [],
            },
        )

    client = _client(handler)

    resultado = client.buscar_ativos("petr")

    assert len(resultado) == 1
    assert resultado[0].ticker == "PETR4"
    assert resultado[0].nome == "PETROBRAS PN"
    assert resultado[0].tipo is TipoAtivo.ACAO
    assert resultado[0].moeda == "BRL"
    assert resultado[0].setor == "Petroleo e Gas"


def test_buscar_ativos_ignora_subtypes_nao_suportados():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "symbol": "ABCP11",
                        "name": "FUNDO FIP TESTE",
                        "assetType": "fund",
                        "subType": "fip",
                        "currency": "BRL",
                        "sector": None,
                    }
                ],
                "indexes": [],
            },
        )

    client = _client(handler)

    assert client.buscar_ativos("abcp") == []


def test_buscar_ativos_envia_bearer_token_quando_api_key_configurada():
    autorizacao_recebida = {}

    def handler(request: httpx.Request) -> httpx.Response:
        autorizacao_recebida["valor"] = request.headers.get("Authorization")
        return httpx.Response(200, json={"results": [], "indexes": []})

    client = _client(handler, api_key="meu-token")
    client.buscar_ativos("petr")

    assert autorizacao_recebida["valor"] == "Bearer meu-token"


def test_buscar_ativos_sem_api_key_nao_envia_header_authorization():
    autorizacao_recebida = {}

    def handler(request: httpx.Request) -> httpx.Response:
        autorizacao_recebida["valor"] = request.headers.get("Authorization")
        return httpx.Response(200, json={"results": [], "indexes": []})

    client = _client(handler, api_key=None)
    client.buscar_ativos("petr")

    assert autorizacao_recebida["valor"] is None


def test_buscar_ativos_com_erro_http_lanca_brapi_indisponivel():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": True, "message": "erro interno"})

    client = _client(handler)

    with pytest.raises(BrapiIndisponivelError):
        client.buscar_ativos("petr")


def test_buscar_ativos_com_erro_de_rede_lanca_brapi_indisponivel():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("conexao recusada", request=request)

    client = _client(handler)

    with pytest.raises(BrapiIndisponivelError):
        client.buscar_ativos("petr")


def test_buscar_cotacao_atual_mapeia_a_resposta_da_brapi():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["symbols"] == "PETR4"
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "requestedSymbol": "PETR4",
                        "symbol": "PETR4",
                        "changed": False,
                        "data": {
                            "shortName": "PETR4",
                            "longName": "Petrobras",
                            "currency": "BRL",
                            "regularMarketPrice": 36.65,
                            "regularMarketDayHigh": 37.10,
                            "regularMarketDayLow": 36.20,
                            "regularMarketChange": -0.35,
                            "regularMarketChangePercent": -0.95,
                            "regularMarketTime": "2026-09-09T20:00:00.000Z",
                            "regularMarketVolume": 27681100,
                        },
                    }
                ],
                "requestedAt": "2026-09-09T20:00:01.000Z",
                "took": "12ms",
            },
        )

    client = _client(handler)

    cotacao = client.buscar_cotacao_atual("PETR4")

    assert cotacao.ticker == "PETR4"
    assert float(cotacao.preco) == pytest.approx(36.65)
    assert float(cotacao.variacao) == pytest.approx(-0.35)
    assert float(cotacao.variacao_percentual) == pytest.approx(-0.95)
    assert float(cotacao.maxima_dia) == pytest.approx(37.10)
    assert float(cotacao.minima_dia) == pytest.approx(36.20)
    assert float(cotacao.volume) == pytest.approx(27681100)


def test_buscar_cotacao_atual_com_ticker_inexistente_lanca_erro_especifico():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": True, "message": "nao encontrado"})

    client = _client(handler)

    with pytest.raises(TickerNaoEncontradoError):
        client.buscar_cotacao_atual("NAOEXISTE")


def test_buscar_cotacao_atual_com_erro_do_servidor_lanca_brapi_indisponivel():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": True, "message": "erro interno"})

    client = _client(handler)

    with pytest.raises(BrapiIndisponivelError):
        client.buscar_cotacao_atual("PETR4")


def test_buscar_cotacao_atual_com_results_vazio_lanca_erro_especifico():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": []})

    client = _client(handler)

    with pytest.raises(TickerNaoEncontradoError):
        client.buscar_cotacao_atual("NAOEXISTE")


def test_buscar_historico_mapeia_os_pontos_da_serie():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["symbols"] == "PETR4"
        assert request.url.params["range"] == "1mo"
        assert request.url.params["interval"] == "1d"
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "symbol": "PETR4",
                        "data": {
                            "historicalDataPrice": [
                                {
                                    "date": 1704067200,
                                    "open": 35.0,
                                    "high": 36.0,
                                    "low": 34.5,
                                    "close": 35.8,
                                    "volume": 1000000,
                                    "adjustedClose": 35.8,
                                }
                            ],
                        },
                    }
                ]
            },
        )

    client = _client(handler)

    pontos = client.buscar_historico("PETR4", PeriodoHistorico.UM_MES)

    assert len(pontos) == 1
    assert float(pontos[0].abertura) == pytest.approx(35.0)
    assert float(pontos[0].maxima) == pytest.approx(36.0)
    assert float(pontos[0].minima) == pytest.approx(34.5)
    assert float(pontos[0].fechamento) == pytest.approx(35.8)
    assert float(pontos[0].volume) == pytest.approx(1000000)
    assert pontos[0].data.year == 2024


def test_buscar_historico_com_ticker_inexistente_lanca_erro_especifico():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": True, "message": "nao encontrado"})

    client = _client(handler)

    with pytest.raises(TickerNaoEncontradoError):
        client.buscar_historico("NAOEXISTE", PeriodoHistorico.UM_MES)


def test_buscar_historico_com_results_vazio_lanca_erro_especifico():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": []})

    client = _client(handler)

    with pytest.raises(TickerNaoEncontradoError):
        client.buscar_historico("NAOEXISTE", PeriodoHistorico.UM_MES)
