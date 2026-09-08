from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID


@dataclass
class Cotacao:
    id: UUID
    ativo_id: UUID
    data_hora: datetime
    abertura: Decimal
    maxima: Decimal
    minima: Decimal
    fechamento: Decimal
    volume: Decimal
