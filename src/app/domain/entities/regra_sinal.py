from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID


@dataclass
class RegraSinal:
    id: UUID
    nome: str
    descricao: str
    condicoes: dict
    peso: Decimal
    ativa: bool = True
