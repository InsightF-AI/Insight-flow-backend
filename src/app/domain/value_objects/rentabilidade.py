from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class Rentabilidade:
    custo_base_brl: Decimal
    valor_mercado_brl: Decimal
    lucro_nao_realizado_brl: Decimal
    lucro_realizado_brl: Decimal
    percentual: Decimal
