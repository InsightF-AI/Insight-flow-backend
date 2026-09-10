from datetime import UTC, datetime
from decimal import Decimal

from app.domain.enums.periodo_historico import PeriodoHistorico
from app.domain.enums.tipo_ativo import TipoAtivo
from app.integrations.brapi.client import AtivoEncontrado, CotacaoAtual, PontoHistorico
from app.services.cached_dados_mercado_service import CachedDadosMercadoService
from tests.fixtures.fake_dados_mercado_service import FakeDadosMercadoService
from tests.fixtures.fake_mercado_cache import FakeMercadoCache

_COTACAO_PETR4 = CotacaoAtual(
    ticker="PETR4",
    preco=Decimal("36.65"),
    variacao=Decimal("-0.35"),
    variacao_percentual=Decimal("-0.95"),
    maxima_dia=Decimal("37.10"),
    minima_dia=Decimal("36.20"),
    volume=Decimal(27681100),
)

_PONTO_PETR4 = PontoHistorico(
    data=datetime(2024, 1, 1, tzinfo=UTC),
    abertura=Decimal(35),
    maxima=Decimal(36),
    minima=Decimal("34.5"),
    fechamento=Decimal("35.8"),
    volume=Decimal(1000000),
)

_TTL_COTACAO_ATUAL = 60


def _service(interno=None, cache=None) -> CachedDadosMercadoService:
    return CachedDadosMercadoService(
        interno or FakeDadosMercadoService(),
        cache or FakeMercadoCache(),
        ttl_cotacao_atual=_TTL_COTACAO_ATUAL,
    )


def test_cotacao_atual_com_cache_vazio_busca_no_interno_e_povoa_o_cache():
    interno = FakeDadosMercadoService(cotacoes={"PETR4": _COTACAO_PETR4})
    cache = FakeMercadoCache()
    service = _service(interno, cache)

    resultado = service.buscar_cotacao_atual("PETR4")

    assert resultado == _COTACAO_PETR4
    assert cache.obter("cotacao_atual:PETR4") is not None


def test_cotacao_atual_com_cache_populado_nao_chama_o_interno():
    interno = FakeDadosMercadoService(cotacoes={"PETR4": _COTACAO_PETR4})
    cache = FakeMercadoCache()
    service = _service(interno, cache)
    service.buscar_cotacao_atual("PETR4")

    interno._cotacoes.clear()
    resultado = service.buscar_cotacao_atual("PETR4")

    assert resultado == _COTACAO_PETR4


def test_historico_com_cache_vazio_busca_no_interno_e_povoa_o_cache():
    interno = FakeDadosMercadoService(historicos={"PETR4": [_PONTO_PETR4]})
    cache = FakeMercadoCache()
    service = _service(interno, cache)

    resultado = service.buscar_historico("PETR4", PeriodoHistorico.UM_MES)

    assert resultado == [_PONTO_PETR4]
    assert cache.obter("historico:PETR4:1M") is not None


def test_historico_usa_o_ttl_curto_independente_do_periodo():
    interno = FakeDadosMercadoService(historicos={"PETR4": [_PONTO_PETR4]})
    cache = FakeMercadoCache()
    service = _service(interno, cache)

    for periodo in PeriodoHistorico:
        service.buscar_historico("PETR4", periodo)

    assert set(cache.ttls.values()) == {_TTL_COTACAO_ATUAL}


def test_historico_com_cache_populado_nao_chama_o_interno():
    interno = FakeDadosMercadoService(historicos={"PETR4": [_PONTO_PETR4]})
    cache = FakeMercadoCache()
    service = _service(interno, cache)
    service.buscar_historico("PETR4", PeriodoHistorico.UM_MES)

    interno._historicos.clear()
    resultado = service.buscar_historico("PETR4", PeriodoHistorico.UM_MES)

    assert resultado == [_PONTO_PETR4]


def test_buscar_ativo_nunca_usa_o_cache():
    encontrado = AtivoEncontrado(
        ticker="PETR4", nome="Petrobras PN", tipo=TipoAtivo.ACAO, moeda="BRL", setor="Petroleo"
    )
    interno = FakeDadosMercadoService(catalogo=[encontrado])
    cache = FakeMercadoCache()
    service = _service(interno, cache)

    resultado = service.buscar_ativo("PETR4")

    assert resultado == [encontrado]
    assert cache._valores == {}
