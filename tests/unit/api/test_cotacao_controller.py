from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from app.domain.entities.ativo import Ativo
from app.domain.enums.tipo_ativo import TipoAtivo
from app.integrations.brapi.client import CotacaoAtual, PontoHistorico

_PETR4 = Ativo(
    id=uuid4(),
    ticker="PETR4",
    nome="Petrobras PN",
    tipo=TipoAtivo.ACAO,
    setor="Petroleo e Gas",
    moeda="BRL",
    fonte_dados="brapi",
)

_COTACAO_PETR4 = CotacaoAtual(
    ticker="PETR4",
    preco=Decimal("36.65"),
    variacao=Decimal("-0.35"),
    variacao_percentual=Decimal("-0.95"),
    maxima_dia=Decimal("37.10"),
    minima_dia=Decimal("36.20"),
    volume=Decimal(27681100),
)


def test_cotacao_atual_sem_token_retorna_401(client, ativo_repository):
    ativo_repository.salvar(_PETR4)

    resposta = client.get(f"/api/v1/ativos/{_PETR4.id}/cotacao")

    assert resposta.status_code == 401


def test_cotacao_atual_retorna_dados_do_ativo(
    client, auth_headers, ativo_repository, cotacoes_brapi
):
    ativo_repository.salvar(_PETR4)
    cotacoes_brapi["PETR4"] = _COTACAO_PETR4

    resposta = client.get(f"/api/v1/ativos/{_PETR4.id}/cotacao", headers=auth_headers)

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["ticker"] == "PETR4"
    assert corpo["preco"] == "36.65"


def test_cotacao_atual_de_ativo_inexistente_retorna_404(client, auth_headers):
    resposta = client.get(f"/api/v1/ativos/{uuid4()}/cotacao", headers=auth_headers)

    assert resposta.status_code == 404


def test_cotacao_atual_sem_cotacao_disponivel_retorna_404(client, auth_headers, ativo_repository):
    ativo_repository.salvar(_PETR4)

    resposta = client.get(f"/api/v1/ativos/{_PETR4.id}/cotacao", headers=auth_headers)

    assert resposta.status_code == 404


def test_cotacao_atual_com_brapi_indisponivel_retorna_503(
    client, auth_headers, ativo_repository, dados_mercado_service
):
    ativo_repository.salvar(_PETR4)
    dados_mercado_service.indisponivel = True

    resposta = client.get(f"/api/v1/ativos/{_PETR4.id}/cotacao", headers=auth_headers)

    assert resposta.status_code == 503


def test_historico_retorna_a_serie_do_ativo(
    client, auth_headers, ativo_repository, historicos_brapi
):
    ativo_repository.salvar(_PETR4)
    historicos_brapi["PETR4"] = [
        PontoHistorico(
            data=datetime(2024, 1, 1, tzinfo=UTC),
            abertura=Decimal(35),
            maxima=Decimal(36),
            minima=Decimal("34.5"),
            fechamento=Decimal("35.8"),
            volume=Decimal(1000000),
        )
    ]

    resposta = client.get(
        f"/api/v1/ativos/{_PETR4.id}/historico",
        params={"periodo": "1M"},
        headers=auth_headers,
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert len(corpo) == 1
    assert corpo[0]["fechamento"] == "35.8"


def test_historico_de_ativo_inexistente_retorna_404(client, auth_headers):
    resposta = client.get(
        f"/api/v1/ativos/{uuid4()}/historico",
        params={"periodo": "1M"},
        headers=auth_headers,
    )

    assert resposta.status_code == 404


def test_historico_sem_serie_disponivel_retorna_404(client, auth_headers, ativo_repository):
    ativo_repository.salvar(_PETR4)

    resposta = client.get(
        f"/api/v1/ativos/{_PETR4.id}/historico",
        params={"periodo": "1M"},
        headers=auth_headers,
    )

    assert resposta.status_code == 404
