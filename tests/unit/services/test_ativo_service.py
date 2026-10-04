from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.entities.ativo import Ativo
from app.domain.enums.periodo_historico import PeriodoHistorico
from app.domain.enums.tipo_ativo import TipoAtivo
from app.domain.value_objects.politica_historico import PoliticaHistorico
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


_POLITICA = PoliticaHistorico(
    periodo_backfill=PeriodoHistorico.TRES_MESES,
    periodo_backfill_cripto=PeriodoHistorico.CINCO_ANOS,
    minimo_cotacoes=50,
)

_POLITICA_CINCO_ANOS = PoliticaHistorico(
    periodo_backfill=PeriodoHistorico.CINCO_ANOS,
    periodo_backfill_cripto=PeriodoHistorico.CINCO_ANOS,
    minimo_cotacoes=50,
)

_BTC = Ativo(
    id=uuid4(),
    ticker="BTC",
    nome="BTC",
    tipo=TipoAtivo.CRIPTO,
    setor=None,
    moeda="BRL",
    fonte_dados="binance",
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


def _ponto_dias_atras(dias: int, fechamento: str) -> PontoHistorico:
    return PontoHistorico(
        data=datetime.now(UTC) - timedelta(days=dias),
        abertura=Decimal(fechamento),
        maxima=Decimal(fechamento),
        minima=Decimal(fechamento),
        fechamento=Decimal(fechamento),
        volume=Decimal(1000),
    )


def test_historico_de_um_dia_retorna_o_ponto_da_cotacao_atual_sem_persistir():
    ativo_repository = FakeAtivoRepository()
    ativo_repository.salvar(_PETR4)
    cotacao = CotacaoAtual(
        ticker="PETR4",
        preco=Decimal("36.65"),
        variacao=Decimal("-0.35"),
        variacao_percentual=Decimal("-0.95"),
        maxima_dia=Decimal("37.10"),
        minima_dia=Decimal("36.20"),
        volume=Decimal(27681100),
        abertura=Decimal("36.90"),
    )
    dados_mercado_service = FakeDadosMercadoService(cotacoes={"PETR4": cotacao})
    cotacao_repository = FakeCotacaoRepository()
    service = _service(ativo_repository, dados_mercado_service, cotacao_repository)

    resultado = service.historico(_PETR4.id, PeriodoHistorico.UM_DIA)

    assert len(resultado) == 1
    assert resultado[0].abertura == Decimal("36.90")
    assert resultado[0].maxima == Decimal("37.10")
    assert resultado[0].minima == Decimal("36.20")
    assert resultado[0].fechamento == Decimal("36.65")
    assert resultado[0].volume == Decimal(27681100)
    assert dados_mercado_service.historicos_solicitados == []
    assert cotacao_repository.listar_por_ativo(_PETR4.id) == []


def test_historico_de_um_dia_sem_abertura_usa_o_preco_atual():
    ativo_repository = FakeAtivoRepository()
    ativo_repository.salvar(_PETR4)
    dados_mercado_service = FakeDadosMercadoService(cotacoes={"PETR4": _COTACAO_PETR4})
    service = _service(ativo_repository, dados_mercado_service)

    resultado = service.historico(_PETR4.id, PeriodoHistorico.UM_DIA)

    assert resultado[0].abertura == _COTACAO_PETR4.preco


def test_historico_de_um_ano_atualiza_tres_meses_e_le_do_banco_dentro_do_corte():
    ativo_repository = FakeAtivoRepository()
    ativo_repository.salvar(_PETR4)
    dados_mercado_service = FakeDadosMercadoService(
        historicos={"PETR4": [_ponto_dias_atras(10, "40")]}
    )
    cotacao_repository = FakeCotacaoRepository()
    cotacao_repository.salvar_muitas(
        [
            AtivoService._para_cotacao(_PETR4.id, _ponto_dias_atras(400, "30")),
            AtivoService._para_cotacao(_PETR4.id, _ponto_dias_atras(200, "35")),
        ]
    )
    service = _service(ativo_repository, dados_mercado_service, cotacao_repository)

    resultado = service.historico(_PETR4.id, PeriodoHistorico.UM_ANO)

    assert dados_mercado_service.historicos_solicitados == [("PETR4", PeriodoHistorico.TRES_MESES)]
    assert [p.fechamento for p in resultado] == [Decimal(35), Decimal(40)]


def test_historico_de_cinco_anos_le_do_banco_com_corte_de_cinco_anos():
    ativo_repository = FakeAtivoRepository()
    ativo_repository.salvar(_PETR4)
    dados_mercado_service = FakeDadosMercadoService(
        historicos={
            "PETR4": [
                _ponto_dias_atras(2000, "20"),
                _ponto_dias_atras(400, "30"),
                _ponto_dias_atras(10, "40"),
            ]
        }
    )
    service = _service(ativo_repository, dados_mercado_service)

    resultado = service.historico(_PETR4.id, PeriodoHistorico.CINCO_ANOS)

    assert [p.fechamento for p in resultado] == [Decimal(30), Decimal(40)]


def test_historico_nao_persiste_quando_nao_ha_pontos():
    ativo_repository = FakeAtivoRepository()
    ativo_repository.salvar(_PETR4)
    dados_mercado_service = FakeDadosMercadoService(historicos={"PETR4": []})
    cotacao_repository = FakeCotacaoRepository()
    service = _service(ativo_repository, dados_mercado_service, cotacao_repository)

    service.historico(_PETR4.id, PeriodoHistorico.UM_MES)

    assert cotacao_repository.listar_por_ativo(_PETR4.id) == []


def _pontos(quantidade: int) -> list[PontoHistorico]:
    return [
        PontoHistorico(
            data=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=i),
            abertura=Decimal("36.00"),
            maxima=Decimal("37.00"),
            minima=Decimal("35.50"),
            fechamento=Decimal("36.50"),
            volume=Decimal(1000),
        )
        for i in range(quantidade)
    ]


def test_atualizar_historico_com_poucas_cotacoes_busca_periodo_de_backfill():
    ativo_repository = FakeAtivoRepository()
    ativo_repository.salvar(_PETR4)
    dados_mercado_service = FakeDadosMercadoService(historicos={"PETR4": _pontos(63)})
    cotacao_repository = FakeCotacaoRepository()
    service = _service(ativo_repository, dados_mercado_service, cotacao_repository)

    service.atualizar_historico(_PETR4.id, _POLITICA)

    assert dados_mercado_service.historicos_solicitados == [("PETR4", PeriodoHistorico.TRES_MESES)]
    assert len(cotacao_repository.listar_por_ativo(_PETR4.id)) == 63


def test_atualizar_historico_com_cotacoes_suficientes_busca_apenas_um_mes():
    ativo_repository = FakeAtivoRepository()
    ativo_repository.salvar(_PETR4)
    dados_mercado_service = FakeDadosMercadoService(historicos={"PETR4": _pontos(50)})
    cotacao_repository = FakeCotacaoRepository()
    service = _service(ativo_repository, dados_mercado_service, cotacao_repository)
    service.historico(_PETR4.id, PeriodoHistorico.TRES_MESES)
    dados_mercado_service.historicos_solicitados.clear()

    service.atualizar_historico(_PETR4.id, _POLITICA)

    assert dados_mercado_service.historicos_solicitados == [("PETR4", PeriodoHistorico.UM_MES)]


def test_buscar_ou_criar_indice_cria_o_ativo_de_referencia_uma_unica_vez():
    ativo_repository = FakeAtivoRepository()
    service = _service(ativo_repository)

    primeiro = service.buscar_ou_criar_indice("^BVSP", "Ibovespa")
    segundo = service.buscar_ou_criar_indice("^BVSP", "Ibovespa")

    assert primeiro.id == segundo.id
    assert primeiro.tipo is TipoAtivo.INDICE
    assert primeiro.moeda == "BRL"
    assert ativo_repository.buscar_por_ticker("^BVSP") == primeiro


def test_coleta_de_historico_nao_diario_nao_persiste():
    ativo_repository = FakeAtivoRepository()
    ativo_repository.salvar(_PETR4)
    dados_mercado_service = FakeDadosMercadoService(
        historicos={"PETR4": [_ponto_dias_atras(3000, "20")]}
    )
    cotacao_repository = FakeCotacaoRepository()
    service = _service(ativo_repository, dados_mercado_service, cotacao_repository)

    service.atualizar_historico(_PETR4.id, _POLITICA_CINCO_ANOS)

    assert cotacao_repository.listar_por_ativo(_PETR4.id) == []


def test_coleta_de_historico_persiste_quando_a_fonte_diz_que_e_diario():
    ativo_repository = FakeAtivoRepository()
    ativo_repository.salvar(_PETR4)
    dados_mercado_service = FakeDadosMercadoService(
        historicos={"PETR4": [_ponto_dias_atras(3000, "20")]}, tickers_diarios={"PETR4"}
    )
    cotacao_repository = FakeCotacaoRepository()
    service = _service(ativo_repository, dados_mercado_service, cotacao_repository)

    service.atualizar_historico(_PETR4.id, _POLITICA_CINCO_ANOS)

    assert len(cotacao_repository.listar_por_ativo(_PETR4.id)) == 1


def test_atualizar_historico_de_cripto_com_poucas_cotacoes_busca_cinco_anos_e_persiste():
    ativo_repository = FakeAtivoRepository()
    ativo_repository.salvar(_BTC)
    dados_mercado_service = FakeDadosMercadoService(
        historicos={"BTC": [_ponto_dias_atras(900, "200000"), _ponto_dias_atras(1, "450000")]},
        tickers_diarios={"BTC"},
    )
    cotacao_repository = FakeCotacaoRepository()
    service = _service(ativo_repository, dados_mercado_service, cotacao_repository)

    service.atualizar_historico(_BTC.id, _POLITICA)

    assert dados_mercado_service.historicos_solicitados == [("BTC", PeriodoHistorico.CINCO_ANOS)]
    assert len(cotacao_repository.listar_por_ativo(_BTC.id)) == 2
