from app.domain.enums.tipo_ativo import TipoAtivo
from app.integrations.brapi.client import AtivoEncontrado

_PETR4 = AtivoEncontrado(
    ticker="PETR4", nome="Petrobras PN", tipo=TipoAtivo.ACAO, moeda="BRL", setor="Petroleo e Gas"
)


def test_buscar_sem_token_retorna_401(client):
    resposta = client.get("/api/v1/ativos/buscar", params={"termo": "petr"})

    assert resposta.status_code == 401


def test_buscar_com_token_retorna_candidatos(client, auth_headers, catalogo_brapi):
    catalogo_brapi.append(_PETR4)

    resposta = client.get("/api/v1/ativos/buscar", params={"termo": "petr"}, headers=auth_headers)

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert len(corpo) == 1
    assert corpo[0]["ticker"] == "PETR4"


def test_buscar_sem_correspondencia_retorna_lista_vazia(client, auth_headers):
    resposta = client.get(
        "/api/v1/ativos/buscar", params={"termo": "naoexiste"}, headers=auth_headers
    )

    assert resposta.status_code == 200
    assert resposta.json() == []


def test_buscar_com_brapi_indisponivel_retorna_503(client, auth_headers, dados_mercado_service):
    dados_mercado_service.indisponivel = True

    resposta = client.get("/api/v1/ativos/buscar", params={"termo": "petr"}, headers=auth_headers)

    assert resposta.status_code == 503
