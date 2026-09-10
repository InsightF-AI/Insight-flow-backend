from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from app.domain.entities.regra_sinal import RegraSinal

REGRAS_PADRAO: list[RegraSinal] = [
    RegraSinal(
        id=UUID("a1a1a1a1-0000-0000-0000-000000000001"),
        nome="Sobrevenda RSI",
        descricao="RSI(14) abaixo de 30 — condição técnica de sobrevenda.",
        condicoes={
            "tipo_indicador": "RSI",
            "parametros": {"periodo": 14},
            "operador": "menor_que",
            "valor_limiar": 30,
        },
        peso=Decimal("1.0"),
    ),
    RegraSinal(
        id=UUID("a1a1a1a1-0000-0000-0000-000000000002"),
        nome="Sobrecompra RSI",
        descricao="RSI(14) acima de 70 — condição técnica de sobrecompra.",
        condicoes={
            "tipo_indicador": "RSI",
            "parametros": {"periodo": 14},
            "operador": "maior_que",
            "valor_limiar": 70,
        },
        peso=Decimal("1.0"),
    ),
    RegraSinal(
        id=UUID("a1a1a1a1-0000-0000-0000-000000000003"),
        nome="Pico de Volume",
        descricao=(
            "Volume relativo(20) acima de 1.5x a média — atividade de negociação incomum."
        ),
        condicoes={
            "tipo_indicador": "VOLUME_RELATIVO",
            "parametros": {"periodo": 20},
            "operador": "maior_que",
            "valor_limiar": 1.5,
        },
        peso=Decimal("0.5"),
    ),
]


def buscar_regra_por_id(regra_id: UUID) -> RegraSinal | None:
    for regra in REGRAS_PADRAO:
        if regra.id == regra_id:
            return regra
    return None
