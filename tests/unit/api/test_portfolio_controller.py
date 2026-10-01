from decimal import Decimal
from uuid import uuid4

from app.domain.entities.ativo import Ativo
from app.domain.enums.tipo_ativo import TipoAtivo
from app.integrations.brapi.client import CotacaoAtual

_PETR4 = Ativo(
    id=uuid4(),
    ticker="PETR4",
    nome="Petrobras PN",
    tipo=TipoAtivo.ACAO,
    setor="Petroleo e Gas",
    moeda="BRL",
    fonte_dados="manual",
)


def test_registrar_operacao_ativo_inexistente_retorna_404(client, auth_headers):
    resposta = client.post(
        "/api/v1/operacoes",
        json={
            "ativo_id": str(uuid4()),
            "tipo": "COMPRA",
            "quantidade": "10",
            "preco_unitario": "30.00",
            "data": "2026-09-01",
        },
        headers=auth_headers,
    )

    assert resposta.status_code == 404


def test_registrar_operacao_quantidade_zero_retorna_422(client, auth_headers, ativo_repository):
    ativo_repository.salvar(_PETR4)

    resposta = client.post(
        "/api/v1/operacoes",
        json={
            "ativo_id": str(_PETR4.id),
            "tipo": "COMPRA",
            "quantidade": "0",
            "preco_unitario": "30.00",
            "data": "2026-09-01",
        },
        headers=auth_headers,
    )

    assert resposta.status_code == 422


def test_registrar_operacao_data_futura_retorna_422(client, auth_headers, ativo_repository):
    ativo_repository.salvar(_PETR4)

    resposta = client.post(
        "/api/v1/operacoes",
        json={
            "ativo_id": str(_PETR4.id),
            "tipo": "COMPRA",
            "quantidade": "10",
            "preco_unitario": "30.00",
            "data": "2100-01-01",
        },
        headers=auth_headers,
    )

    assert resposta.status_code == 422


def test_registrar_venda_sem_posicao_retorna_422(client, auth_headers, ativo_repository):
    ativo_repository.salvar(_PETR4)

    resposta = client.post(
        "/api/v1/operacoes",
        json={
            "ativo_id": str(_PETR4.id),
            "tipo": "VENDA",
            "quantidade": "10",
            "preco_unitario": "30.00",
            "data": "2026-09-01",
        },
        headers=auth_headers,
    )

    assert resposta.status_code == 422


def test_remover_operacao_de_outro_usuario_retorna_404(
    client, auth_headers, auth_headers_outro_usuario, ativo_repository
):
    ativo_repository.salvar(_PETR4)
    criado = client.post(
        "/api/v1/operacoes",
        json={
            "ativo_id": str(_PETR4.id),
            "tipo": "COMPRA",
            "quantidade": "10",
            "preco_unitario": "30.00",
            "data": "2026-09-01",
        },
        headers=auth_headers,
    )
    operacao_id = criado.json()["id"]

    resposta = client.delete(
        f"/api/v1/operacoes/{operacao_id}", headers=auth_headers_outro_usuario
    )

    assert resposta.status_code == 404


def test_remover_operacao_que_invalida_sequencia_restante_retorna_422(
    client, auth_headers, ativo_repository
):
    ativo_repository.salvar(_PETR4)
    compra = client.post(
        "/api/v1/operacoes",
        json={
            "ativo_id": str(_PETR4.id),
            "tipo": "COMPRA",
            "quantidade": "10",
            "preco_unitario": "30.00",
            "data": "2026-09-01",
        },
        headers=auth_headers,
    )
    operacao_id = compra.json()["id"]
    client.post(
        "/api/v1/operacoes",
        json={
            "ativo_id": str(_PETR4.id),
            "tipo": "VENDA",
            "quantidade": "10",
            "preco_unitario": "50.00",
            "data": "2026-09-02",
        },
        headers=auth_headers,
    )

    resposta = client.delete(f"/api/v1/operacoes/{operacao_id}", headers=auth_headers)

    assert resposta.status_code == 422
    assert len(client.get("/api/v1/operacoes", headers=auth_headers).json()) == 2


def test_comparativo_benchmark_sem_operacoes_retorna_404(client, auth_headers):
    resposta = client.get(
        "/api/v1/portfolio/benchmark", params={"benchmark": "CDI"}, headers=auth_headers
    )

    assert resposta.status_code == 404


def test_registrar_compra_e_consultar_posicoes_retorna_200_com_um_item(
    client, auth_headers, ativo_repository, cotacoes_brapi
):
    ativo_repository.salvar(_PETR4)
    cotacoes_brapi["PETR4"] = CotacaoAtual(
        ticker="PETR4",
        preco=Decimal("50.00"),
        variacao=Decimal(0),
        variacao_percentual=Decimal(0),
        maxima_dia=Decimal("50.00"),
        minima_dia=Decimal("50.00"),
        volume=Decimal(0),
    )

    registro = client.post(
        "/api/v1/operacoes",
        json={
            "ativo_id": str(_PETR4.id),
            "tipo": "COMPRA",
            "quantidade": "10",
            "preco_unitario": "30.00",
            "data": "2026-09-01",
        },
        headers=auth_headers,
    )
    assert registro.status_code == 201

    resposta = client.get("/api/v1/portfolio/posicoes", headers=auth_headers)

    assert resposta.status_code == 200
    posicoes = resposta.json()
    assert len(posicoes) == 1
    assert posicoes[0]["ativo_id"] == str(_PETR4.id)
