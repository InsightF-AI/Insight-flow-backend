import httpx
import pytest

from app.domain.enums.tipo_ativo import TipoAtivo
from app.integrations.brapi.client import BrapiClient, BrapiIndisponivelError


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
