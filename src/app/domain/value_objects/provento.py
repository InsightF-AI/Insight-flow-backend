from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True)
class Provento:
    data_ex: date
    valor_por_cota: Decimal


@dataclass(frozen=True)
class ProventoRecebido:
    ativo_id: UUID
    ticker: str
    data_ex: date
    valor_por_cota: Decimal
    quantidade: Decimal
    total_brl: Decimal


@dataclass(frozen=True)
class ResumoProventos:
    total_brl: Decimal
    proventos: list[ProventoRecebido]
