from uuid import uuid4

from app.domain.entities.ativo import Ativo
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


def _ativo(ticker: str, tipo: TipoAtivo) -> Ativo:
    return Ativo(
        id=uuid4(),
        ticker=ticker,
        nome=f"Nome {ticker}",
        tipo=tipo,
        setor=None,
        moeda="BRL",
        fonte_dados="binance" if tipo is TipoAtivo.CRIPTO else "brapi",
    )


def test_catalogo_sem_token_retorna_401(client):
    resposta = client.get("/api/v1/ativos/catalogo")

    assert resposta.status_code == 401


def test_catalogo_lista_ativos_cadastrados_em_ordem_de_ticker_sem_indices(
    client, auth_headers, ativo_repository
):
    vale = _ativo("VALE3", TipoAtivo.ACAO)
    btc = _ativo("BTC", TipoAtivo.CRIPTO)
    ativo_repository.salvar(vale)
    ativo_repository.salvar(_ativo("^BVSP", TipoAtivo.INDICE))
    ativo_repository.salvar(btc)

    resposta = client.get("/api/v1/ativos/catalogo", headers=auth_headers)

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert [item["ticker"] for item in corpo] == ["BTC", "VALE3"]
    assert corpo[0] == {
        "id": str(btc.id),
        "ticker": "BTC",
        "nome": "Nome BTC",
        "tipo": "CRIPTO",
        "setor": None,
        "moeda": "BRL",
    }


def test_catalogo_filtra_por_tipo(client, auth_headers, ativo_repository):
    ativo_repository.salvar(_ativo("VALE3", TipoAtivo.ACAO))
    ativo_repository.salvar(_ativo("BTC", TipoAtivo.CRIPTO))

    resposta = client.get(
        "/api/v1/ativos/catalogo", params={"tipo": "CRIPTO"}, headers=auth_headers
    )

    assert resposta.status_code == 200
    assert [item["ticker"] for item in resposta.json()] == ["BTC"]
