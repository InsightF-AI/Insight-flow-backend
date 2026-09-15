from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID


@dataclass
class ResultadoBacktest:
    regra_id: UUID
    ativo_id: UUID
    total_ocorrencias: int
    retorno_medio_5_pregoes: Decimal | None
    retorno_medio_20_pregoes: Decimal | None
    retorno_medio_60_pregoes: Decimal | None
