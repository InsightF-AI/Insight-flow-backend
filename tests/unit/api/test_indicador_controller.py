from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from app.domain.entities.ativo import Ativo
from app.domain.entities.cotacao import Cotacao
from app.domain.enums.tipo_ativo import TipoAtivo

_PETR4 = Ativo(
    id=uuid4(),
    ticker="PETR4",
    nome="Petrobras PN",
    tipo=TipoAtivo.ACAO,
    setor="Petroleo e Gas",
    moeda="BRL",
    fonte_dados="brapi",
)


def _cotacoes_diarias(dias: int) -> list[Cotacao]:
    base = datetime(2024, 1, 1, tzinfo=UTC)
    return [
        Cotacao(
            id=uuid4(),
            ativo_id=_PETR4.id,
            data_hora=base + timedelta(days=i),
            abertura=Decimal(str(10 + i * 0.1)),
            maxima=Decimal(str(10 + i * 0.1)),
            minima=Decimal(str(10 + i * 0.1)),
            fechamento=Decimal(str(10 + i * 0.1)),
            volume=Decimal(1000000),
        )
        for i in range(dias)
    ]


def test_indicadores_sem_token_retorna_401(client, ativo_repository):
    ativo_repository.salvar(_PETR4)

    resposta = client.get(f"/api/v1/ativos/{_PETR4.id}/indicadores")

    assert resposta.status_code == 401


def test_indicadores_calcula_e_retorna_para_o_ativo(
    client, auth_headers, ativo_repository, cotacao_repository
):
    ativo_repository.salvar(_PETR4)
    cotacao_repository.salvar_muitas(_cotacoes_diarias(60))

    resposta = client.get(f"/api/v1/ativos/{_PETR4.id}/indicadores", headers=auth_headers)

    assert resposta.status_code == 200
    corpo = resposta.json()
    tipos = {item["tipo"] for item in corpo}
    assert "SMA" in tipos
    assert "RSI" in tipos


def test_indicadores_de_ativo_inexistente_retorna_404(client, auth_headers):
    resposta = client.get(f"/api/v1/ativos/{uuid4()}/indicadores", headers=auth_headers)

    assert resposta.status_code == 404
