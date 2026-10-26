from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.domain.entities.ativo import Ativo
from app.domain.enums.tipo_ativo import TipoAtivo
from app.domain.value_objects.provento import Provento
from app.integrations.yahoo.client import YahooIndisponivelError

_PETR4 = Ativo(
    id=uuid4(),
    ticker="PETR4",
    nome="Petrobras PN",
    tipo=TipoAtivo.ACAO,
    setor="Petroleo e Gas",
    moeda="BRL",
    fonte_dados="brapi",
)


def test_dividendos_do_ativo_vem_do_mais_recente_para_o_mais_antigo(
    client, auth_headers, ativo_repository, fonte_proventos
):
    ativo_repository.salvar(_PETR4)
    fonte_proventos.proventos["PETR4"] = [
        Provento(date(2026, 3, 2), Decimal("0.5")),
        Provento(date(2026, 8, 24), Decimal("0.47156696")),
    ]

    resposta = client.get(f"/api/v1/ativos/{_PETR4.id}/dividendos", headers=auth_headers)

    assert resposta.status_code == 200
    assert resposta.json() == [
        {"data_ex": "2026-08-24", "valor_por_cota": "0.47156696"},
        {"data_ex": "2026-03-02", "valor_por_cota": "0.5"},
    ]


def test_dividendos_de_ativo_inexistente_retorna_404(client, auth_headers):
    resposta = client.get(f"/api/v1/ativos/{uuid4()}/dividendos", headers=auth_headers)

    assert resposta.status_code == 404


def test_dividendos_com_fonte_fora_do_ar_retorna_503(
    client, auth_headers, ativo_repository, fonte_proventos
):
    ativo_repository.salvar(_PETR4)
    fonte_proventos.erro = YahooIndisponivelError()

    resposta = client.get(f"/api/v1/ativos/{_PETR4.id}/dividendos", headers=auth_headers)

    assert resposta.status_code == 503


def test_dividendos_exige_autenticacao(client):
    assert client.get(f"/api/v1/ativos/{uuid4()}/dividendos").status_code == 401


def test_dividendos_recebidos_da_carteira(client, auth_headers, ativo_repository, fonte_proventos):
    ativo_repository.salvar(_PETR4)
    fonte_proventos.proventos["PETR4"] = [Provento(date(2026, 9, 15), Decimal("0.25"))]
    client.post(
        "/api/v1/operacoes",
        json={
            "ativo_id": str(_PETR4.id),
            "tipo": "COMPRA",
            "quantidade": "100",
            "preco_unitario": "30.00",
            "data": "2026-09-01",
        },
        headers=auth_headers,
    )

    resposta = client.get("/api/v1/portfolio/dividendos", headers=auth_headers)

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert Decimal(corpo["total_brl"]) == Decimal(25)
    assert corpo["proventos"][0]["ticker"] == "PETR4"
    assert corpo["proventos"][0]["data_ex"] == "2026-09-15"
    assert Decimal(corpo["proventos"][0]["quantidade"]) == Decimal(100)


def test_dividendos_recebidos_sem_operacoes(client, auth_headers):
    resposta = client.get("/api/v1/portfolio/dividendos", headers=auth_headers)

    assert resposta.status_code == 200
    assert resposta.json() == {"total_brl": "0", "proventos": []}
