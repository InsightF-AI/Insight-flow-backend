from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.entities.alerta_personalizado import AlertaPersonalizado
from app.domain.enums.tipo_condicao_alerta import TipoCondicaoAlerta


def _criar_alerta(
    tipo_condicao=TipoCondicaoAlerta.PRECO_MAIOR_IGUAL,
    valor_alvo=Decimal("40.00"),
):
    return AlertaPersonalizado.criar(
        id=uuid4(),
        usuario_id=uuid4(),
        ativo_id=uuid4(),
        tipo_condicao=tipo_condicao,
        valor_alvo=valor_alvo,
        criado_em=datetime(2026, 9, 8, 12, 0, 0),
    )


def test_criar_com_valor_alvo_zero_ou_negativo_levanta_erro():
    with pytest.raises(ValueError):
        AlertaPersonalizado.criar(
            id=uuid4(),
            usuario_id=uuid4(),
            ativo_id=uuid4(),
            tipo_condicao=TipoCondicaoAlerta.PRECO_MAIOR_IGUAL,
            valor_alvo=Decimal("0"),
            criado_em=datetime(2026, 9, 8, 12, 0, 0),
        )


def test_avaliar_dispara_quando_preco_atinge_condicao_maior_igual():
    alerta = _criar_alerta(valor_alvo=Decimal("40.00"))
    agora = datetime(2026, 9, 8, 13, 0, 0)

    disparou = alerta.avaliar(Decimal("40.00"), agora)

    assert disparou is True
    assert alerta.disparado_em == agora


def test_avaliar_nao_dispara_enquanto_preco_nao_atinge_a_condicao():
    alerta = _criar_alerta(valor_alvo=Decimal("40.00"))

    disparou = alerta.avaliar(Decimal("39.99"), datetime(2026, 9, 8, 13, 0, 0))

    assert disparou is False
    assert alerta.disparado_em is None


def test_avaliar_nao_dispara_novamente_enquanto_condicao_permanece_atendida():
    alerta = _criar_alerta(valor_alvo=Decimal("40.00"))
    alerta.avaliar(Decimal("40.00"), datetime(2026, 9, 8, 13, 0, 0))

    disparou_de_novo = alerta.avaliar(Decimal("41.00"), datetime(2026, 9, 8, 13, 5, 0))

    assert disparou_de_novo is False


def test_avaliar_dispara_novamente_apos_condicao_deixar_de_ser_atendida_e_voltar():
    alerta = _criar_alerta(valor_alvo=Decimal("40.00"))
    alerta.avaliar(Decimal("40.00"), datetime(2026, 9, 8, 13, 0, 0))
    alerta.avaliar(Decimal("39.00"), datetime(2026, 9, 8, 13, 5, 0))

    disparou_de_novo = alerta.avaliar(Decimal("40.50"), datetime(2026, 9, 8, 13, 10, 0))

    assert disparou_de_novo is True


def test_avaliar_com_condicao_menor_igual():
    alerta = _criar_alerta(
        tipo_condicao=TipoCondicaoAlerta.PRECO_MENOR_IGUAL,
        valor_alvo=Decimal("35.00"),
    )

    disparou = alerta.avaliar(Decimal("34.90"), datetime(2026, 9, 8, 13, 0, 0))

    assert disparou is True


def test_alerta_inativo_nao_dispara():
    alerta = _criar_alerta(valor_alvo=Decimal("40.00"))
    alerta.ativo = False

    disparou = alerta.avaliar(Decimal("41.00"), datetime(2026, 9, 8, 13, 0, 0))

    assert disparou is False


def test_rearmar_limpa_estado_permitindo_novo_disparo_na_mesma_condicao():
    alerta = _criar_alerta(valor_alvo=Decimal("40.00"))
    alerta.avaliar(Decimal("40.00"), datetime(2026, 9, 8, 13, 0, 0))

    alerta.rearmar()
    disparou_de_novo = alerta.avaliar(Decimal("41.00"), datetime(2026, 9, 8, 13, 30, 0))

    assert disparou_de_novo is True
