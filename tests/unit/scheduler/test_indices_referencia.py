from datetime import UTC, datetime
from decimal import Decimal

from app.domain.enums.periodo_historico import PeriodoHistorico
from app.domain.enums.tipo_ativo import TipoAtivo
from app.domain.value_objects.politica_historico import PoliticaHistorico
from app.integrations.brapi.client import PontoHistorico
from app.scheduler.indices_referencia import atualizar_indices_referencia
from app.services.ativo_service import AtivoService
from tests.fixtures.fake_ativo_repository import FakeAtivoRepository
from tests.fixtures.fake_cotacao_repository import FakeCotacaoRepository
from tests.fixtures.fake_dados_mercado_service import FakeDadosMercadoService

_PONTO = PontoHistorico(
    data=datetime(2026, 10, 2, tzinfo=UTC),
    abertura=Decimal(190000),
    maxima=Decimal(193000),
    minima=Decimal(189000),
    fechamento=Decimal(192115),
    volume=Decimal(0),
)


_POLITICA = PoliticaHistorico(
    periodo_backfill=PeriodoHistorico.TRES_MESES,
    periodo_backfill_cripto=PeriodoHistorico.CINCO_ANOS,
    minimo_cotacoes=50,
)


def test_cria_o_ibovespa_e_persiste_o_historico_de_backfill():
    ativo_repository = FakeAtivoRepository()
    cotacao_repository = FakeCotacaoRepository()
    dados_mercado_service = FakeDadosMercadoService(historicos={"^BVSP": [_PONTO]})
    ativo_service = AtivoService(ativo_repository, dados_mercado_service, cotacao_repository)

    atualizar_indices_referencia(ativo_service, _POLITICA)

    ibovespa = ativo_repository.buscar_por_ticker("^BVSP")
    assert ibovespa.tipo is TipoAtivo.INDICE
    assert dados_mercado_service.historicos_solicitados == [("^BVSP", PeriodoHistorico.TRES_MESES)]
    assert len(cotacao_repository.listar_por_ativo(ibovespa.id)) == 1


def test_brapi_indisponivel_nao_propaga_o_erro():
    ativo_service = AtivoService(
        FakeAtivoRepository(),
        FakeDadosMercadoService(indisponivel=True),
        FakeCotacaoRepository(),
    )

    atualizar_indices_referencia(ativo_service, _POLITICA)
