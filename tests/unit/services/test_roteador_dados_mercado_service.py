import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.domain.enums.periodo_historico import PeriodoHistorico
from app.domain.enums.tipo_ativo import TipoAtivo
from app.integrations.binance.client import BinanceIndisponivelError
from app.integrations.brapi.client import AtivoEncontrado, CotacaoAtual, PontoHistorico
from app.services.roteador_dados_mercado_service import RoteadorDadosMercadoService
from tests.fixtures.fake_binance_client import FakeBinanceClient
from tests.fixtures.fake_dados_mercado_service import FakeDadosMercadoService
from tests.fixtures.fake_mercado_cache import FakeMercadoCache

_PETR4 = AtivoEncontrado(
    ticker="PETR4", nome="Petrobras PN", tipo=TipoAtivo.ACAO, moeda="BRL", setor="Petroleo e Gas"
)


def _cotacao(ticker: str, preco: str) -> CotacaoAtual:
    return CotacaoAtual(
        ticker=ticker,
        preco=Decimal(preco),
        variacao=Decimal(0),
        variacao_percentual=Decimal(0),
        maxima_dia=Decimal(preco),
        minima_dia=Decimal(preco),
        volume=Decimal(1),
    )


def _ponto(fechamento: str) -> PontoHistorico:
    return PontoHistorico(
        data=datetime(2026, 10, 1, tzinfo=UTC),
        abertura=Decimal(fechamento),
        maxima=Decimal(fechamento),
        minima=Decimal(fechamento),
        fechamento=Decimal(fechamento),
        volume=Decimal(1),
    )


def _roteador(brapi=None, binance=None, cache=None) -> RoteadorDadosMercadoService:
    return RoteadorDadosMercadoService(
        brapi or FakeDadosMercadoService(),
        binance or FakeBinanceClient(),
        cache or FakeMercadoCache(),
        ttl_catalogo_segundos=86400,
    )


def test_cotacao_de_cripto_vem_da_binance_e_de_acao_vem_da_brapi():
    roteador = _roteador(
        brapi=FakeDadosMercadoService(cotacoes={"PETR4": _cotacao("PETR4", "36")}),
        binance=FakeBinanceClient(pares=["BTC"], cotacoes={"BTC": _cotacao("BTC", "450000")}),
    )

    assert roteador.buscar_cotacao_atual("BTC").preco == Decimal(450000)
    assert roteador.buscar_cotacao_atual("PETR4").preco == Decimal(36)


def test_historico_de_cripto_vem_da_binance_e_de_acao_vem_da_brapi():
    brapi = FakeDadosMercadoService(historicos={"PETR4": [_ponto("36")]})
    roteador = _roteador(
        brapi=brapi,
        binance=FakeBinanceClient(pares=["BTC"], historicos={"BTC": [_ponto("450000")]}),
    )

    btc = roteador.buscar_historico("BTC", PeriodoHistorico.UM_MES)
    petr4 = roteador.buscar_historico("PETR4", PeriodoHistorico.UM_MES)

    assert btc[0].fechamento == Decimal(450000)
    assert petr4[0].fechamento == Decimal(36)
    assert brapi.historicos_solicitados == [("PETR4", PeriodoHistorico.UM_MES)]


def test_busca_junta_brapi_e_criptos_que_contem_o_termo_sem_diferenciar_maiusculas():
    roteador = _roteador(
        brapi=FakeDadosMercadoService([_PETR4]),
        binance=FakeBinanceClient(pares=["BTC", "ETH", "USDT"]),
    )

    encontrados = roteador.buscar_ativo("t")

    assert [a.ticker for a in encontrados] == ["PETR4", "BTC", "ETH", "USDT"]
    btc = encontrados[1]
    assert btc.tipo is TipoAtivo.CRIPTO
    assert btc.moeda == "BRL"
    assert btc.setor is None
    assert btc.nome == "BTC"
    assert btc.fonte_dados == "binance"
    assert [a.ticker for a in roteador.buscar_ativo("btc")] == ["BTC"]


def test_busca_segue_so_com_a_brapi_quando_a_binance_esta_fora():
    roteador = _roteador(
        brapi=FakeDadosMercadoService([_PETR4]),
        binance=FakeBinanceClient(indisponivel=True),
    )

    assert [a.ticker for a in roteador.buscar_ativo("petr")] == ["PETR4"]


def test_catalogo_e_gravado_no_cache_com_o_ttl_e_reaproveitado():
    cache = FakeMercadoCache()
    binance = FakeBinanceClient(pares=["BTC"], cotacoes={"BTC": _cotacao("BTC", "450000")})
    roteador = _roteador(binance=binance, cache=cache)

    roteador.buscar_cotacao_atual("BTC")
    roteador.buscar_cotacao_atual("BTC")

    assert binance.chamadas_catalogo == 1
    assert json.loads(cache.obter("catalogo_cripto_brl")) == ["BTC"]
    assert cache.ttls["catalogo_cripto_brl"] == 86400


def test_falha_ao_montar_o_catalogo_nao_grava_cache_e_propaga_na_cotacao():
    cache = FakeMercadoCache()
    roteador = _roteador(binance=FakeBinanceClient(indisponivel=True), cache=cache)

    with pytest.raises(BinanceIndisponivelError):
        roteador.buscar_cotacao_atual("BTC")

    assert cache.obter("catalogo_cripto_brl") is None


def test_historico_e_diario_e_sempre_verdadeiro_para_cripto_e_delega_para_acao():
    roteador = _roteador(binance=FakeBinanceClient(pares=["BTC"]))

    assert roteador.historico_e_diario("BTC", PeriodoHistorico.CINCO_ANOS) is True
    assert roteador.historico_e_diario("PETR4", PeriodoHistorico.CINCO_ANOS) is False
    assert roteador.historico_e_diario("PETR4", PeriodoHistorico.TRES_MESES) is True


def test_acoes_e_indices_nao_dependem_da_binance():
    binance = FakeBinanceClient(indisponivel=True)
    roteador = _roteador(
        brapi=FakeDadosMercadoService(
            cotacoes={"PETR4": _cotacao("PETR4", "36"), "^BVSP": _cotacao("^BVSP", "192000")},
            historicos={"PETR4": [_ponto("36")]},
        ),
        binance=binance,
    )

    assert roteador.buscar_cotacao_atual("PETR4").preco == Decimal(36)
    assert roteador.buscar_cotacao_atual("^BVSP").preco == Decimal(192000)
    assert roteador.buscar_historico("PETR4", PeriodoHistorico.UM_MES)[0].fechamento == Decimal(36)
    assert roteador.historico_e_diario("PETR4", PeriodoHistorico.TRES_MESES) is True
    assert binance.chamadas_catalogo == 0
