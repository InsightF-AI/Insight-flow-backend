from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from app.domain.entities.cotacao import Cotacao


def test_cria_cotacao_com_todos_os_atributos_ohlcv():
    ativo_id = uuid4()
    momento = datetime(2026, 9, 8, 18, 0, 0)

    cotacao = Cotacao(
        id=uuid4(),
        ativo_id=ativo_id,
        data_hora=momento,
        abertura=Decimal("38.50"),
        maxima=Decimal("39.10"),
        minima=Decimal("38.20"),
        fechamento=Decimal("38.90"),
        volume=Decimal("125000000"),
    )

    assert cotacao.ativo_id == ativo_id
    assert cotacao.fechamento == Decimal("38.90")
    assert cotacao.data_hora == momento
