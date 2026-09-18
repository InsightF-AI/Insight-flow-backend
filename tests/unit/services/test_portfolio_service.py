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
