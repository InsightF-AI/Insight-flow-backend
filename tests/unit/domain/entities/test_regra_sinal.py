from decimal import Decimal
from uuid import uuid4

from app.domain.entities.regra_sinal import RegraSinal


def test_cria_regra_sinal_ativa_por_padrao():
    regra = RegraSinal(
        id=uuid4(),
        nome="Sobrevenda RSI",
        descricao="RSI abaixo de 30 nos últimos 14 períodos",
        condicoes={"indicador": "RSI", "operador": "<", "valor": 30},
        peso=Decimal("1.0"),
    )

    assert regra.ativa is True
    assert regra.peso == Decimal("1.0")
