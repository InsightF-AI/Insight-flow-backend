from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from app.api.deps import get_sinal_service
from app.domain.entities.ativo import Ativo
from app.domain.entities.cotacao import Cotacao
from app.domain.entities.sinal import Sinal
from app.domain.enums.tipo_ativo import TipoAtivo
from app.domain.regras_sinal_padrao import REGRAS_PADRAO
from app.main import app

_PETR4 = Ativo(
    id=uuid4(),
    ticker="PETR4",
    nome="Petrobras PN",
    tipo=TipoAtivo.ACAO,
    setor="Petroleo e Gas",
    moeda="BRL",
    fonte_dados="brapi",
)

_REGRA_SOBREVENDA_RSI = next(r for r in REGRAS_PADRAO if r.nome == "Sobrevenda RSI")


def _cotacoes_rsi_baixo(ativo_id, dias: int) -> list[Cotacao]:
    precos = [20.0] * (dias - 10) + [20 - i * 1.0 for i in range(1, 11)]
    base = datetime.now(UTC) - timedelta(days=len(precos) - 1)
    return [
        Cotacao(
            id=uuid4(),
            ativo_id=ativo_id,
            data_hora=base + timedelta(days=i),
            abertura=Decimal(str(preco)),
            maxima=Decimal(str(preco)),
            minima=Decimal(str(preco)),
            fechamento=Decimal(str(preco)),
            volume=Decimal(1000000),
        )
        for i, preco in enumerate(precos)
    ]


def test_sinais_sem_token_retorna_401(client, ativo_repository):
    ativo_repository.salvar(_PETR4)

    resposta = client.get(f"/api/v1/ativos/{_PETR4.id}/sinais")

    assert resposta.status_code == 401


def test_sinais_avalia_e_retorna_sinais_vigentes(client, auth_headers, ativo_repository, cotacao_repository):
    ativo_repository.salvar(_PETR4)
    cotacao_repository.salvar_muitas(_cotacoes_rsi_baixo(_PETR4.id, 40))

    resposta = client.get(f"/api/v1/ativos/{_PETR4.id}/sinais", headers=auth_headers)

    assert resposta.status_code == 200
    corpo = resposta.json()
    nomes = {item["regra_nome"] for item in corpo}
    assert "Sobrevenda RSI" in nomes


class _ServicoComSinalOrfao:
    def __init__(self, sinais: list[Sinal]) -> None:
        self._sinais = sinais

    def avaliar_ativo(self, ativo_id):
        return self._sinais


def test_sinais_ignora_sinal_com_regra_removida(client, auth_headers, ativo_repository):
    ativo_repository.salvar(_PETR4)

    sinal_valido = Sinal(
        id=uuid4(),
        ativo_id=_PETR4.id,
        regra_id=_REGRA_SOBREVENDA_RSI.id,
        data_ativacao=datetime.now(UTC),
        contexto={},
        data_desativacao=None,
    )
    sinal_orfao = Sinal(
        id=uuid4(),
        ativo_id=_PETR4.id,
        regra_id=uuid4(),
        data_ativacao=datetime.now(UTC),
        contexto={},
        data_desativacao=None,
    )

    app.dependency_overrides[get_sinal_service] = lambda: _ServicoComSinalOrfao(
        [sinal_valido, sinal_orfao]
    )
    try:
        resposta = client.get(f"/api/v1/ativos/{_PETR4.id}/sinais", headers=auth_headers)
    finally:
        del app.dependency_overrides[get_sinal_service]

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert len(corpo) == 1
    assert corpo[0]["regra_id"] == str(_REGRA_SOBREVENDA_RSI.id)


def test_sinais_de_ativo_inexistente_retorna_404(client, auth_headers):
    resposta = client.get(f"/api/v1/ativos/{uuid4()}/sinais", headers=auth_headers)

    assert resposta.status_code == 404


def test_backtest_retorna_resultado(client, auth_headers, ativo_repository, cotacao_repository):
    ativo_repository.salvar(_PETR4)
    cotacao_repository.salvar_muitas(_cotacoes_rsi_baixo(_PETR4.id, 40))

    resposta = client.get(
        f"/api/v1/ativos/{_PETR4.id}/sinais/{_REGRA_SOBREVENDA_RSI.id}/backtest",
        headers=auth_headers,
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["regra_id"] == str(_REGRA_SOBREVENDA_RSI.id)
    assert corpo["total_ocorrencias"] >= 1


def test_backtest_com_regra_inexistente_retorna_404(client, auth_headers, ativo_repository):
    ativo_repository.salvar(_PETR4)

    resposta = client.get(
        f"/api/v1/ativos/{_PETR4.id}/sinais/{uuid4()}/backtest",
        headers=auth_headers,
    )

    assert resposta.status_code == 404


def test_backtest_com_ativo_inexistente_retorna_404(client, auth_headers):
    resposta = client.get(
        f"/api/v1/ativos/{uuid4()}/sinais/{_REGRA_SOBREVENDA_RSI.id}/backtest",
        headers=auth_headers,
    )

    assert resposta.status_code == 404
