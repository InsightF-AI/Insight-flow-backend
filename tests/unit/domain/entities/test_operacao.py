from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from app.domain.entities.operacao import Operacao
from app.domain.enums.tipo_operacao import TipoOperacao


def test_valor_total_multiplica_quantidade_pelo_preco_unitario():
    operacao = Operacao(
        id=uuid4(),
        usuario_id=uuid4(),
        ativo_id=uuid4(),
        tipo=TipoOperacao.COMPRA,
        quantidade=Decimal(100),
        preco_unitario=Decimal("38.50"),
        data=date(2026, 9, 8),
        criado_em=datetime(2026, 9, 8, 18, 0, 0, tzinfo=UTC),
    )

    assert operacao.valor_total() == Decimal("3850.00")
