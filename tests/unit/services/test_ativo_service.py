from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.entities.ativo import Ativo
from app.domain.enums.periodo_historico import PeriodoHistorico
from app.domain.enums.tipo_ativo import TipoAtivo
from app.integrations.brapi.client import CotacaoAtual, PontoHistorico
from app.services.ativo_service import AtivoService
from app.services.exceptions import AtivoNaoEncontradoError
from tests.fixtures.fake_ativo_repository import FakeAtivoRepository
from tests.fixtures.fake_cotacao_repository import FakeCotacaoRepository
from tests.fixtures.fake_dados_mercado_service import FakeDadosMercadoService

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


def _service(
    ativo_repository=None, dados_mercado_service=None, cotacao_repository=None
) -> AtivoService:
    return AtivoService(
        ativo_repository or FakeAtivoRepository(),
        dados_mercado_service or FakeDadosMercadoService(),
        cotacao_repository or FakeCotacaoRepository(),
    )


def test_cotacao_atual_resolve_o_ticker_e_delega_para_dados_mercado():
    ativo_repository = FakeAtivoRepository()
    ativo_repository.salvar(_PETR4)
    dados_mercado_service = FakeDadosMercadoService(cotacoes={"PETR4": _COTACAO_PETR4})
    service = _service(ativo_repository, dados_mercado_service)

    cotacao = service.cotacao_atual(_PETR4.id)

    assert cotacao == _COTACAO_PETR4


def test_cotacao_atual_com_ativo_inexistente_lanca_erro():
    service = _service()

    with pytest.raises(AtivoNaoEncontradoError):
        service.cotacao_atual(uuid4())


def test_historico_resolve_o_ticker_e_delega_para_dados_mercado():
    ativo_repository = FakeAtivoRepository()
    ativo_repository.salvar(_PETR4)
    ponto = PontoHistorico(
        data=datetime(2024, 1, 1, tzinfo=UTC),
        abertura=Decimal(35),
        maxima=Decimal(36),
        minima=Decimal("34.5"),
        fechamento=Decimal("35.8"),
        volume=Decimal(1000000),
    )
    dados_mercado_service = FakeDadosMercadoService(historicos={"PETR4": [ponto]})
    service = _service(ativo_repository, dados_mercado_service)

    resultado = service.historico(_PETR4.id, PeriodoHistorico.UM_MES)

    assert resultado == [ponto]


def test_historico_com_ativo_inexistente_lanca_erro():
    service = _service()

    with pytest.raises(AtivoNaoEncontradoError):
        service.historico(uuid4(), PeriodoHistorico.UM_MES)


def test_historico_persiste_as_cotacoes_retornadas_no_repositorio():
    ativo_repository = FakeAtivoRepository()
    ativo_repository.salvar(_PETR4)
    ponto = PontoHistorico(
        data=datetime(2024, 1, 1, tzinfo=UTC),
        abertura=Decimal(35),
        maxima=Decimal(36),
        minima=Decimal("34.5"),
        fechamento=Decimal("35.8"),
        volume=Decimal(1000000),
    )
    dados_mercado_service = FakeDadosMercadoService(historicos={"PETR4": [ponto]})
    cotacao_repository = FakeCotacaoRepository()
    service = _service(ativo_repository, dados_mercado_service, cotacao_repository)

    service.historico(_PETR4.id, PeriodoHistorico.UM_MES)

    persistidas = cotacao_repository.listar_por_ativo(_PETR4.id)
    assert len(persistidas) == 1
    assert persistidas[0].ativo_id == _PETR4.id
    assert persistidas[0].data_hora == ponto.data
    assert persistidas[0].fechamento == ponto.fechamento
    assert persistidas[0].volume == ponto.volume


def test_historico_nao_persiste_quando_nao_ha_pontos():
    ativo_repository = FakeAtivoRepository()
    ativo_repository.salvar(_PETR4)
    dados_mercado_service = FakeDadosMercadoService(historicos={"PETR4": []})
    cotacao_repository = FakeCotacaoRepository()
    service = _service(ativo_repository, dados_mercado_service, cotacao_repository)

    service.historico(_PETR4.id, PeriodoHistorico.UM_MES)

    assert cotacao_repository.listar_por_ativo(_PETR4.id) == []
