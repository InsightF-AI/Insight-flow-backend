from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.enums.tipo_ativo import TipoAtivo


@dataclass
class Distribuicao:
    por_classe: dict[TipoAtivo, Decimal]
    por_setor: dict[str, Decimal]
    por_moeda: dict[str, Decimal]
