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

    assert estado.quantidade == Decimal("10")
    assert estado.preco_medio == Decimal("30.00")
    assert estado.lucro_realizado == Decimal("0")


def test_compras_multiplas_calculam_media_ponderada():
    operacoes = [
        _operacao(TipoOperacao.COMPRA, "10", "30.00", 1),
        _operacao(TipoOperacao.COMPRA, "10", "40.00", 2),
    ]

    estado = replay_operacoes(operacoes)

    assert estado.quantidade == Decimal("20")
    assert estado.preco_medio == Decimal("35.00")


def test_venda_parcial_nao_altera_preco_medio():
    operacoes = [
        _operacao(TipoOperacao.COMPRA, "10", "30.00", 1),
        _operacao(TipoOperacao.VENDA, "4", "50.00", 2),
    ]

    estado = replay_operacoes(operacoes)

    assert estado.quantidade == Decimal("6")
    assert estado.preco_medio == Decimal("30.00")
    assert estado.lucro_realizado == Decimal("80.00")


def test_venda_total_zera_quantidade_e_reseta_preco_medio():
    operacoes = [
        _operacao(TipoOperacao.COMPRA, "10", "30.00", 1),
        _operacao(TipoOperacao.VENDA, "10", "50.00", 2),
    ]

    estado = replay_operacoes(operacoes)

    assert estado.quantidade == Decimal("0")
    assert estado.preco_medio == Decimal("0")
    assert estado.lucro_realizado == Decimal("200.00")


def test_compra_apos_zerar_nao_herda_media_antiga():
    operacoes = [
        _operacao(TipoOperacao.COMPRA, "10", "30.00", 1),
        _operacao(TipoOperacao.VENDA, "10", "50.00", 2),
        _operacao(TipoOperacao.COMPRA, "5", "80.00", 3),
    ]

    estado = replay_operacoes(operacoes)

    assert estado.quantidade == Decimal("5")
    assert estado.preco_medio == Decimal("80.00")


def test_venda_lucrativa_parcial_nao_estoura_lucro_realizado_mesmo_fora_de_ordem():
    operacoes = [
        _operacao(TipoOperacao.VENDA, "4", "50.00", 2),
        _operacao(TipoOperacao.COMPRA, "10", "30.00", 1),
    ]

    estado = replay_operacoes(operacoes)

    assert estado.quantidade == Decimal("6")
    assert estado.lucro_realizado == Decimal("80.00")


def test_operacoes_no_mesmo_dia_usam_criado_em_como_desempate():
    operacoes = [
        _operacao(TipoOperacao.VENDA, "10", "50.00", 1, criado_em_hora=15),
        _operacao(TipoOperacao.COMPRA, "10", "30.00", 1, criado_em_hora=9),
    ]

    estado = replay_operacoes(operacoes)

    assert estado.quantidade == Decimal("0")
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
        quantidade=Decimal("10"),
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
            quantidade=Decimal("0"),
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
            quantidade=Decimal("10"),
            preco_unitario=Decimal("-1"),
            data=date(2026, 9, 1),
        )


def test_registrar_operacao_data_futura_lanca_erro():
    service = _service()

    with pytest.raises(OperacaoInvalidaError):
        service.registrar_operacao(
            usuario_id=uuid4(),
            ativo_id=_PETR4.id,
            tipo=TipoOperacao.COMPRA,
            quantidade=Decimal("10"),
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
            quantidade=Decimal("10"),
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
            quantidade=Decimal("10"),
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
        quantidade=Decimal("10"),
        preco_unitario=Decimal("30.00"),
        data=date(2026, 9, 1),
    )
    service.registrar_operacao(
        usuario_id=uuid4(),
        ativo_id=_PETR4.id,
        tipo=TipoOperacao.COMPRA,
        quantidade=Decimal("5"),
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
        quantidade=Decimal("10"),
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
        quantidade=Decimal("10"),
        preco_unitario=Decimal("30.00"),
        data=date(2026, 9, 1),
    )

    with pytest.raises(OperacaoNaoEncontradaError):
        service.remover_operacao(outro, operacao.id)


def test_remover_operacao_inexistente_lanca_erro():
    service = _service()

    with pytest.raises(OperacaoNaoEncontradaError):
        service.remover_operacao(uuid4(), uuid4())
