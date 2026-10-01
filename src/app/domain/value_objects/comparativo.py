from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.enums.tipo_benchmark import TipoBenchmark


@dataclass
class Comparativo:
    benchmark: TipoBenchmark
    rentabilidade_carteira_percentual: Decimal
    rentabilidade_benchmark_percentual: Decimal | None
