from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.entities.operacao import Operacao
from app.domain.enums.tipo_operacao import TipoOperacao
from app.services.exceptions import QuantidadeInsuficienteError
from app.services.portfolio_service import replay_operacoes


def _operacao(tipo, quantidade, preco, dia, criado_em_hora=10) -> Operacao:
    return Operacao(
        id=uuid4(),
        usuario_id=uuid4(),
        ativo_id=uuid4(),
        tipo=tipo,
        quantidade=Decimal(quantidade),
        preco_unitario=Decimal(preco),
        data=date(2026, 9, dia),
        criado_em=datetime(2026, 9, dia, criado_em_hora, 0, 0, tzinfo=UTC),
    )


def test_compra_unica_define_quantidade_e_preco_medio():
    estado = replay_operacoes([_operacao(TipoOperacao.COMPRA, "10", "30.00", 1)])

    assert estado.quantidade == Decimal(10)
    assert estado.preco_medio == Decimal("30.00")
    assert estado.lucro_realizado == Decimal(0)


def test_compras_multiplas_calculam_media_ponderada():
    operacoes = [
        _operacao(TipoOperacao.COMPRA, "10", "30.00", 1),
        _operacao(TipoOperacao.COMPRA, "10", "40.00", 2),
    ]

    estado = replay_operacoes(operacoes)

    assert estado.quantidade == Decimal(20)
    assert estado.preco_medio == Decimal("35.00")


def test_venda_parcial_nao_altera_preco_medio():
    operacoes = [
        _operacao(TipoOperacao.COMPRA, "10", "30.00", 1),
        _operacao(TipoOperacao.VENDA, "4", "50.00", 2),
    ]

    estado = replay_operacoes(operacoes)

    assert estado.quantidade == Decimal(6)
    assert estado.preco_medio == Decimal("30.00")
    assert estado.lucro_realizado == Decimal("80.00")


def test_venda_total_zera_quantidade_e_reseta_preco_medio():
    operacoes = [
        _operacao(TipoOperacao.COMPRA, "10", "30.00", 1),
        _operacao(TipoOperacao.VENDA, "10", "50.00", 2),
    ]

    estado = replay_operacoes(operacoes)

    assert estado.quantidade == Decimal(0)
    assert estado.preco_medio == Decimal(0)
    assert estado.lucro_realizado == Decimal("200.00")


def test_compra_apos_zerar_nao_herda_media_antiga():
    operacoes = [
        _operacao(TipoOperacao.COMPRA, "10", "30.00", 1),
        _operacao(TipoOperacao.VENDA, "10", "50.00", 2),
        _operacao(TipoOperacao.COMPRA, "5", "80.00", 3),
    ]

    estado = replay_operacoes(operacoes)

    assert estado.quantidade == Decimal(5)
    assert estado.preco_medio == Decimal("80.00")


def test_venda_lucrativa_parcial_nao_estoura_lucro_realizado_mesmo_fora_de_ordem():
    operacoes = [
        _operacao(TipoOperacao.VENDA, "4", "50.00", 2),
        _operacao(TipoOperacao.COMPRA, "10", "30.00", 1),
    ]

    estado = replay_operacoes(operacoes)

    assert estado.quantidade == Decimal(6)
    assert estado.lucro_realizado == Decimal("80.00")


def test_operacoes_no_mesmo_dia_usam_criado_em_como_desempate():
    operacoes = [
        _operacao(TipoOperacao.VENDA, "10", "50.00", 1, criado_em_hora=15),
        _operacao(TipoOperacao.COMPRA, "10", "30.00", 1, criado_em_hora=9),
    ]

    estado = replay_operacoes(operacoes)

    assert estado.quantidade == Decimal(0)
    assert estado.lucro_realizado == Decimal("200.00")


def test_venda_maior_que_posicao_levanta_quantidade_insuficiente():
    operacoes = [
        _operacao(TipoOperacao.COMPRA, "5", "30.00", 1),
        _operacao(TipoOperacao.VENDA, "10", "50.00", 2),
    ]

    with pytest.raises(QuantidadeInsuficienteError):
        replay_operacoes(operacoes)


from app.domain.entities.ativo import Ativo
from app.domain.enums.tipo_ativo import TipoAtivo
from app.services.exceptions import (
    AtivoNaoEncontradoError,
    OperacaoInvalidaError,
    OperacaoNaoEncontradaError,
)
from app.services.portfolio_service import PortfolioService
from tests.fixtures.fake_ativo_repository import FakeAtivoRepository
from tests.fixtures.fake_cambio_service import FakeCambioService
from tests.fixtures.fake_dados_mercado_service import FakeDadosMercadoService
from tests.fixtures.fake_operacao_repository import FakeOperacaoRepository

_PETR4 = Ativo(
    id=uuid4(),
    ticker="PETR4",
    nome="Petrobras PN",
    tipo=TipoAtivo.ACAO,
    setor="Petroleo e Gas",
    moeda="BRL",
    fonte_dados="manual",
)


def _service(ativos=None):
    ativo_repository = FakeAtivoRepository()
    for ativo in ativos if ativos is not None else [_PETR4]:
        ativo_repository.salvar(ativo)
    return PortfolioService(
        FakeOperacaoRepository(),
        ativo_repository,
        FakeDadosMercadoService(),
        FakeCambioService(),
        bcb_client=None,
    )


def test_registrar_operacao_persiste_compra():
    service = _service()
    usuario_id = uuid4()

    operacao = service.registrar_operacao(
        usuario_id=usuario_id,
        ativo_id=_PETR4.id,
        tipo=TipoOperacao.COMPRA,
        quantidade=Decimal(10),
        preco_unitario=Decimal("30.00"),
        data=date(2026, 9, 1),
    )

    assert operacao.usuario_id == usuario_id
    assert service.listar_operacoes(usuario_id) == [operacao]


def test_registrar_operacao_quantidade_invalida_lanca_erro():
    service = _service()

    with pytest.raises(OperacaoInvalidaError):
        service.registrar_operacao(
            usuario_id=uuid4(),
            ativo_id=_PETR4.id,
            tipo=TipoOperacao.COMPRA,
            quantidade=Decimal(0),
            preco_unitario=Decimal("30.00"),
            data=date(2026, 9, 1),
        )


def test_registrar_operacao_preco_invalido_lanca_erro():
    service = _service()

    with pytest.raises(OperacaoInvalidaError):
        service.registrar_operacao(
            usuario_id=uuid4(),
            ativo_id=_PETR4.id,
            tipo=TipoOperacao.COMPRA,
            quantidade=Decimal(10),
            preco_unitario=Decimal(-1),
            data=date(2026, 9, 1),
        )


def test_registrar_operacao_data_futura_lanca_erro():
    service = _service()

    with pytest.raises(OperacaoInvalidaError):
        service.registrar_operacao(
            usuario_id=uuid4(),
            ativo_id=_PETR4.id,
            tipo=TipoOperacao.COMPRA,
            quantidade=Decimal(10),
            preco_unitario=Decimal("30.00"),
            data=date(2100, 1, 1),
        )


def test_registrar_operacao_ativo_inexistente_lanca_erro():
    service = _service(ativos=[])

    with pytest.raises(AtivoNaoEncontradoError):
        service.registrar_operacao(
            usuario_id=uuid4(),
            ativo_id=_PETR4.id,
            tipo=TipoOperacao.COMPRA,
            quantidade=Decimal(10),
            preco_unitario=Decimal("30.00"),
            data=date(2026, 9, 1),
        )


def test_registrar_venda_sem_posicao_lanca_quantidade_insuficiente():
    service = _service()

    with pytest.raises(QuantidadeInsuficienteError):
        service.registrar_operacao(
            usuario_id=uuid4(),
            ativo_id=_PETR4.id,
            tipo=TipoOperacao.VENDA,
            quantidade=Decimal(10),
            preco_unitario=Decimal("30.00"),
            data=date(2026, 9, 1),
        )


def test_listar_operacoes_retorna_apenas_as_do_usuario():
    service = _service()
    usuario_id = uuid4()
    service.registrar_operacao(
        usuario_id=usuario_id,
        ativo_id=_PETR4.id,
        tipo=TipoOperacao.COMPRA,
        quantidade=Decimal(10),
        preco_unitario=Decimal("30.00"),
        data=date(2026, 9, 1),
    )
    service.registrar_operacao(
        usuario_id=uuid4(),
        ativo_id=_PETR4.id,
        tipo=TipoOperacao.COMPRA,
        quantidade=Decimal(5),
        preco_unitario=Decimal("30.00"),
        data=date(2026, 9, 1),
    )

    assert len(service.listar_operacoes(usuario_id)) == 1


def test_remover_operacao_remove_do_dono():
    service = _service()
    usuario_id = uuid4()
    operacao = service.registrar_operacao(
        usuario_id=usuario_id,
        ativo_id=_PETR4.id,
        tipo=TipoOperacao.COMPRA,
        quantidade=Decimal(10),
        preco_unitario=Decimal("30.00"),
        data=date(2026, 9, 1),
    )

    service.remover_operacao(usuario_id, operacao.id)

    assert service.listar_operacoes(usuario_id) == []


def test_remover_operacao_de_outro_usuario_lanca_erro():
    service = _service()
    dono = uuid4()
    outro = uuid4()
    operacao = service.registrar_operacao(
        usuario_id=dono,
        ativo_id=_PETR4.id,
        tipo=TipoOperacao.COMPRA,
        quantidade=Decimal(10),
        preco_unitario=Decimal("30.00"),
        data=date(2026, 9, 1),
    )

    with pytest.raises(OperacaoNaoEncontradaError):
        service.remover_operacao(outro, operacao.id)


def test_remover_operacao_inexistente_lanca_erro():
    service = _service()

    with pytest.raises(OperacaoNaoEncontradaError):
        service.remover_operacao(uuid4(), uuid4())


from app.integrations.brapi.client import CotacaoAtual


def _cotacao(preco: str) -> CotacaoAtual:
    return CotacaoAtual(
        ticker="PETR4",
        preco=Decimal(preco),
        variacao=Decimal(0),
        variacao_percentual=Decimal(0),
        maxima_dia=Decimal(preco),
        minima_dia=Decimal(preco),
        volume=Decimal(0),
    )


def _service_com_cotacao(preco: str, taxa_cambio: Decimal | None = None) -> PortfolioService:
    ativo_repository = FakeAtivoRepository()
    ativo_repository.salvar(_PETR4)
    return PortfolioService(
        FakeOperacaoRepository(),
        ativo_repository,
        FakeDadosMercadoService(cotacoes={"PETR4": _cotacao(preco)}),
        FakeCambioService(taxa=taxa_cambio if taxa_cambio is not None else Decimal(1)),
        bcb_client=None,
    )


def test_posicoes_calcula_valor_de_mercado_e_lucro_nao_realizado():
    service = _service_com_cotacao(preco="50.00")
    usuario_id = uuid4()
    service.registrar_operacao(
        usuario_id=usuario_id,
        ativo_id=_PETR4.id,
        tipo=TipoOperacao.COMPRA,
        quantidade=Decimal(10),
        preco_unitario=Decimal("30.00"),
        data=date(2026, 9, 1),
    )

    posicoes = service.posicoes(usuario_id)

    assert len(posicoes) == 1
    posicao = posicoes[0]
    assert posicao.ativo_id == _PETR4.id
    assert posicao.quantidade == Decimal(10)
    assert posicao.preco_medio == Decimal("30.00")
    assert posicao.valor_mercado == Decimal("500.00")
    assert posicao.lucro_nao_realizado == Decimal("200.00")
    assert posicao.lucro_realizado == Decimal(0)


def test_posicoes_converte_valor_de_mercado_para_brl():
    ativo_usd = Ativo(
        id=uuid4(),
        ticker="GOOGL",
        nome="Alphabet Inc",
        tipo=TipoAtivo.ACAO,
        setor="Tecnologia",
        moeda="USD",
        fonte_dados="manual",
    )

    ativo_repository = FakeAtivoRepository()
    ativo_repository.salvar(ativo_usd)

    service = PortfolioService(
        FakeOperacaoRepository(),
        ativo_repository,
        FakeDadosMercadoService(
            cotacoes={
                "GOOGL": CotacaoAtual(
                    ticker="GOOGL",
                    preco=Decimal("50.00"),
                    variacao=Decimal(0),
                    variacao_percentual=Decimal(0),
                    maxima_dia=Decimal("50.00"),
                    minima_dia=Decimal("50.00"),
                    volume=Decimal(0),
                )
            }
        ),
        FakeCambioService(taxa=Decimal("5.00")),
        bcb_client=None,
    )

    usuario_id = uuid4()
    service.registrar_operacao(
        usuario_id=usuario_id,
        ativo_id=ativo_usd.id,
        tipo=TipoOperacao.COMPRA,
        quantidade=Decimal(10),
        preco_unitario=Decimal("30.00"),
        data=date(2026, 9, 1),
    )

    posicao = service.posicoes(usuario_id)[0]

    assert posicao.valor_mercado == Decimal("500.00")
    assert posicao.valor_mercado_brl == Decimal("2500.00")


def test_posicoes_omite_ativos_totalmente_vendidos():
    service = _service_com_cotacao(preco="50.00")
    usuario_id = uuid4()
    service.registrar_operacao(
        usuario_id=usuario_id,
        ativo_id=_PETR4.id,
        tipo=TipoOperacao.COMPRA,
        quantidade=Decimal(10),
        preco_unitario=Decimal("30.00"),
        data=date(2026, 9, 1),
    )
    service.registrar_operacao(
        usuario_id=usuario_id,
        ativo_id=_PETR4.id,
        tipo=TipoOperacao.VENDA,
        quantidade=Decimal(10),
        preco_unitario=Decimal("50.00"),
        data=date(2026, 9, 2),
    )

    assert service.posicoes(usuario_id) == []


def test_posicoes_isola_por_usuario():
    service = _service_com_cotacao(preco="50.00")
    dono = uuid4()
    outro = uuid4()
    service.registrar_operacao(
        usuario_id=dono,
        ativo_id=_PETR4.id,
        tipo=TipoOperacao.COMPRA,
        quantidade=Decimal(10),
        preco_unitario=Decimal("30.00"),
        data=date(2026, 9, 1),
    )

    assert service.posicoes(outro) == []


def test_rentabilidade_calcula_percentual_sobre_custo_base():
    service = _service_com_cotacao(preco="50.00")
    usuario_id = uuid4()
    service.registrar_operacao(
        usuario_id=usuario_id,
        ativo_id=_PETR4.id,
        tipo=TipoOperacao.COMPRA,
        quantidade=Decimal(10),
        preco_unitario=Decimal("30.00"),
        data=date(2026, 9, 1),
    )

    rentabilidade = service.rentabilidade(usuario_id)

    assert rentabilidade.custo_base_brl == Decimal("300.00")
    assert rentabilidade.valor_mercado_brl == Decimal("500.00")
    assert rentabilidade.lucro_nao_realizado_brl == Decimal("200.00")
    assert rentabilidade.percentual == Decimal("200.00") / Decimal("300.00")


def test_rentabilidade_nao_estoura_com_venda_parcial_lucrativa():
    service = _service_com_cotacao(preco="50.00")
    usuario_id = uuid4()
    service.registrar_operacao(
        usuario_id=usuario_id,
        ativo_id=_PETR4.id,
        tipo=TipoOperacao.COMPRA,
        quantidade=Decimal(10),
        preco_unitario=Decimal("10.00"),
        data=date(2026, 9, 1),
    )
    service.registrar_operacao(
        usuario_id=usuario_id,
        ativo_id=_PETR4.id,
        tipo=TipoOperacao.VENDA,
        quantidade=Decimal(5),
        preco_unitario=Decimal("30.00"),
        data=date(2026, 9, 2),
    )

    rentabilidade = service.rentabilidade(usuario_id)

    assert rentabilidade.lucro_realizado_brl == Decimal("100.00")
    assert rentabilidade.percentual >= Decimal(0)
    assert rentabilidade.percentual < Decimal(10)


def test_rentabilidade_inclui_lucro_realizado_de_ativo_totalmente_vendido():
    service = _service_com_cotacao(preco="50.00")
    usuario_id = uuid4()
    service.registrar_operacao(
        usuario_id=usuario_id,
        ativo_id=_PETR4.id,
        tipo=TipoOperacao.COMPRA,
        quantidade=Decimal(10),
        preco_unitario=Decimal("30.00"),
        data=date(2026, 9, 1),
    )
    service.registrar_operacao(
        usuario_id=usuario_id,
        ativo_id=_PETR4.id,
        tipo=TipoOperacao.VENDA,
        quantidade=Decimal(10),
        preco_unitario=Decimal("50.00"),
        data=date(2026, 9, 2),
    )

    rentabilidade = service.rentabilidade(usuario_id)

    assert rentabilidade.lucro_realizado_brl == Decimal("200.00")
    assert rentabilidade.custo_base_brl == Decimal(0)
    assert rentabilidade.percentual == Decimal(0)


def test_rentabilidade_sem_operacoes_retorna_zeros():
    service = _service_com_cotacao(preco="50.00")

    rentabilidade = service.rentabilidade(uuid4())

    assert rentabilidade.custo_base_brl == Decimal(0)
    assert rentabilidade.valor_mercado_brl == Decimal(0)
    assert rentabilidade.percentual == Decimal(0)


_VALE3 = Ativo(
    id=uuid4(),
    ticker="VALE3",
    nome="Vale ON",
    tipo=TipoAtivo.ACAO,
    setor="Mineracao",
    moeda="BRL",
    fonte_dados="manual",
)

_BTC = Ativo(
    id=uuid4(),
    ticker="BTC",
    nome="Bitcoin",
    tipo=TipoAtivo.CRIPTO,
    setor=None,
    moeda="USD",
    fonte_dados="manual",
)


def test_distribuicao_agrupa_por_classe_setor_e_moeda_somando_um():
    ativo_repository = FakeAtivoRepository()
    for ativo in (_PETR4, _VALE3, _BTC):
        ativo_repository.salvar(ativo)
    service = PortfolioService(
        FakeOperacaoRepository(),
        ativo_repository,
        FakeDadosMercadoService(
            cotacoes={
                "PETR4": _cotacao("50.00"),
                "VALE3": CotacaoAtual(
                    ticker="VALE3",
                    preco=Decimal("50.00"),
                    variacao=Decimal(0),
                    variacao_percentual=Decimal(0),
                    maxima_dia=Decimal("50.00"),
                    minima_dia=Decimal("50.00"),
                    volume=Decimal(0),
                ),
                "BTC": CotacaoAtual(
                    ticker="BTC",
                    preco=Decimal("100.00"),
                    variacao=Decimal(0),
                    variacao_percentual=Decimal(0),
                    maxima_dia=Decimal("100.00"),
                    minima_dia=Decimal("100.00"),
                    volume=Decimal(0),
                ),
            }
        ),
        FakeCambioService(taxa=Decimal("5.00")),
        bcb_client=None,
    )
    usuario_id = uuid4()
    for ativo_id, preco in ((_PETR4.id, "30.00"), (_VALE3.id, "30.00"), (_BTC.id, "1.00")):
        service.registrar_operacao(
            usuario_id=usuario_id,
            ativo_id=ativo_id,
            tipo=TipoOperacao.COMPRA,
            quantidade=Decimal(10),
            preco_unitario=Decimal(preco),
            data=date(2026, 9, 1),
        )

    distribuicao = service.distribuicao(usuario_id)

    assert sum(distribuicao.por_classe.values()) == Decimal(1)
    assert sum(distribuicao.por_setor.values()) == Decimal(1)
    assert sum(distribuicao.por_moeda.values()) == Decimal(1)
    assert "N/A" in distribuicao.por_setor
    assert distribuicao.por_moeda.keys() == {"BRL", "USD"}


def test_distribuicao_sem_posicoes_retorna_dicionarios_vazios():
    service = _service_com_cotacao(preco="50.00")

    distribuicao = service.distribuicao(uuid4())

    assert distribuicao.por_classe == {}
    assert distribuicao.por_setor == {}
    assert distribuicao.por_moeda == {}


from app.domain.enums.tipo_benchmark import TipoBenchmark
from app.integrations.bcb.client import BcbIndisponivelError, PontoCdi
from app.integrations.brapi.client import PontoHistorico
from app.services.exceptions import PortfolioVazioError


class _FakeBcbClient:
    def __init__(self, pontos: list[PontoCdi] | None = None, indisponivel: bool = False):
        self._pontos = pontos if pontos is not None else []
        self.indisponivel = indisponivel

    def buscar_serie_cdi(self, inicio, fim) -> list[PontoCdi]:
        if self.indisponivel:
            raise BcbIndisponivelError
        return self._pontos


def _service_com_benchmark(bcb_client, historicos=None) -> PortfolioService:
    ativo_repository = FakeAtivoRepository()
    ativo_repository.salvar(_PETR4)
    return PortfolioService(
        FakeOperacaoRepository(),
        ativo_repository,
        FakeDadosMercadoService(
            cotacoes={"PETR4": _cotacao("50.00")}, historicos=historicos or {}
        ),
        FakeCambioService(taxa=Decimal(1)),
        bcb_client=bcb_client,
    )


def test_comparativo_benchmark_sem_operacoes_lanca_erro():
    service = _service_com_benchmark(_FakeBcbClient())

    with pytest.raises(PortfolioVazioError):
        service.comparativo_benchmark(uuid4(), TipoBenchmark.CDI)


def test_comparativo_benchmark_cdi_compoe_taxa_diaria():
    bcb_client = _FakeBcbClient(
        pontos=[
            PontoCdi(data=date(2026, 9, 1), valor=Decimal("0.05")),
            PontoCdi(data=date(2026, 9, 2), valor=Decimal("0.05")),
        ]
    )
    service = _service_com_benchmark(bcb_client)
    usuario_id = uuid4()
    service.registrar_operacao(
        usuario_id=usuario_id,
        ativo_id=_PETR4.id,
        tipo=TipoOperacao.COMPRA,
        quantidade=Decimal(10),
        preco_unitario=Decimal("30.00"),
        data=date(2026, 9, 1),
    )

    comparativo = service.comparativo_benchmark(usuario_id, TipoBenchmark.CDI)

    taxa_esperada = (Decimal("1.0005") * Decimal("1.0005")) - Decimal(1)
    assert comparativo.benchmark == TipoBenchmark.CDI
    assert comparativo.rentabilidade_benchmark_percentual == taxa_esperada


def test_comparativo_benchmark_cdi_indisponivel_retorna_none():
    service = _service_com_benchmark(_FakeBcbClient(indisponivel=True))
    usuario_id = uuid4()
    service.registrar_operacao(
        usuario_id=usuario_id,
        ativo_id=_PETR4.id,
        tipo=TipoOperacao.COMPRA,
        quantidade=Decimal(10),
        preco_unitario=Decimal("30.00"),
        data=date(2026, 9, 1),
    )

    comparativo = service.comparativo_benchmark(usuario_id, TipoBenchmark.CDI)

    assert comparativo.rentabilidade_benchmark_percentual is None
    assert comparativo.rentabilidade_carteira_percentual is not None


def test_comparativo_benchmark_ibovespa_usa_variacao_do_historico():
    historico = [
        PontoHistorico(
            data=datetime(2026, 9, 1, tzinfo=UTC),
            abertura=Decimal(100),
            maxima=Decimal(100),
            minima=Decimal(100),
            fechamento=Decimal(100),
            volume=Decimal(0),
        ),
        PontoHistorico(
            data=datetime(2026, 9, 10, tzinfo=UTC),
            abertura=Decimal(110),
            maxima=Decimal(110),
            minima=Decimal(110),
            fechamento=Decimal(110),
            volume=Decimal(0),
        ),
    ]
    service = _service_com_benchmark(_FakeBcbClient(), historicos={"^BVSP": historico})
    usuario_id = uuid4()
    service.registrar_operacao(
        usuario_id=usuario_id,
        ativo_id=_PETR4.id,
        tipo=TipoOperacao.COMPRA,
        quantidade=Decimal(10),
        preco_unitario=Decimal("30.00"),
        data=date(2026, 9, 1),
    )

    comparativo = service.comparativo_benchmark(usuario_id, TipoBenchmark.IBOVESPA)

    assert comparativo.rentabilidade_benchmark_percentual == Decimal("0.10")


def test_comparativo_benchmark_ibovespa_indisponivel_retorna_none():
    service = _service_com_benchmark(_FakeBcbClient(), historicos={})
    usuario_id = uuid4()
    service.registrar_operacao(
        usuario_id=usuario_id,
        ativo_id=_PETR4.id,
        tipo=TipoOperacao.COMPRA,
        quantidade=Decimal(10),
        preco_unitario=Decimal("30.00"),
        data=date(2026, 9, 1),
    )

    comparativo = service.comparativo_benchmark(usuario_id, TipoBenchmark.IBOVESPA)

    assert comparativo.rentabilidade_benchmark_percentual is None


def test_comparativo_benchmark_cdi_vazio_mas_disponivel_retorna_none():
    service = _service_com_benchmark(_FakeBcbClient(pontos=[]))
    usuario_id = uuid4()
    service.registrar_operacao(
        usuario_id=usuario_id,
        ativo_id=_PETR4.id,
        tipo=TipoOperacao.COMPRA,
        quantidade=Decimal(10),
        preco_unitario=Decimal("30.00"),
        data=date(2026, 9, 1),
    )

    comparativo = service.comparativo_benchmark(usuario_id, TipoBenchmark.CDI)

    assert comparativo.rentabilidade_benchmark_percentual is None


def test_registrar_venda_invalida_cronologicamente_lanca_erro_e_nao_persiste():
    service = _service()
    usuario_id = uuid4()
    service.registrar_operacao(
        usuario_id=usuario_id,
        ativo_id=_PETR4.id,
        tipo=TipoOperacao.COMPRA,
        quantidade=Decimal(10),
        preco_unitario=Decimal("30.00"),
        data=date(2026, 9, 10),
    )

    with pytest.raises(QuantidadeInsuficienteError):
        service.registrar_operacao(
            usuario_id=usuario_id,
            ativo_id=_PETR4.id,
            tipo=TipoOperacao.VENDA,
            quantidade=Decimal(10),
            preco_unitario=Decimal("50.00"),
            data=date(2026, 9, 1),
        )

    operacoes = service.listar_operacoes(usuario_id)
    assert len(operacoes) == 1
    assert operacoes[0].tipo == TipoOperacao.COMPRA


def test_remover_operacao_que_invalida_sequencia_restante_lanca_erro_e_nao_remove():
    service = _service()
    usuario_id = uuid4()
    compra = service.registrar_operacao(
        usuario_id=usuario_id,
        ativo_id=_PETR4.id,
        tipo=TipoOperacao.COMPRA,
        quantidade=Decimal(10),
        preco_unitario=Decimal("30.00"),
        data=date(2026, 9, 1),
    )
    venda = service.registrar_operacao(
        usuario_id=usuario_id,
        ativo_id=_PETR4.id,
        tipo=TipoOperacao.VENDA,
        quantidade=Decimal(10),
        preco_unitario=Decimal("50.00"),
        data=date(2026, 9, 2),
    )

    with pytest.raises(QuantidadeInsuficienteError):
        service.remover_operacao(usuario_id, compra.id)

    operacoes = service.listar_operacoes(usuario_id)
    assert {op.id for op in operacoes} == {compra.id, venda.id}


def test_replay_por_ativo_omite_ativo_corrompido_e_mantem_saudavel():
    ativo_repository = FakeAtivoRepository()
    ativo_repository.salvar(_PETR4)
    operacao_repository = FakeOperacaoRepository()
    service = PortfolioService(
        operacao_repository,
        ativo_repository,
        FakeDadosMercadoService(cotacoes={"PETR4": _cotacao("50.00")}),
        FakeCambioService(taxa=Decimal(1)),
        bcb_client=None,
    )
    usuario_id = uuid4()
    ativo_corrompido_id = uuid4()

    operacao_repository.salvar(
        Operacao(
            id=uuid4(),
            usuario_id=usuario_id,
            ativo_id=ativo_corrompido_id,
            tipo=TipoOperacao.VENDA,
            quantidade=Decimal(10),
            preco_unitario=Decimal("50.00"),
            data=date(2026, 9, 1),
            criado_em=datetime(2026, 9, 1, 10, tzinfo=UTC),
        )
    )
    operacao_repository.salvar(
        Operacao(
            id=uuid4(),
            usuario_id=usuario_id,
            ativo_id=ativo_corrompido_id,
            tipo=TipoOperacao.COMPRA,
            quantidade=Decimal(10),
            preco_unitario=Decimal("30.00"),
            data=date(2026, 9, 10),
            criado_em=datetime(2026, 9, 10, 10, tzinfo=UTC),
        )
    )
    service.registrar_operacao(
        usuario_id=usuario_id,
        ativo_id=_PETR4.id,
        tipo=TipoOperacao.COMPRA,
        quantidade=Decimal(10),
        preco_unitario=Decimal("30.00"),
        data=date(2026, 9, 1),
    )

    posicoes = service.posicoes(usuario_id)

    assert len(posicoes) == 1
    assert posicoes[0].ativo_id == _PETR4.id
