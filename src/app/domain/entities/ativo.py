from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.domain.enums.tipo_ativo import TipoAtivo


@dataclass
class Ativo:
    id: UUID
    ticker: str
    nome: str
    tipo: TipoAtivo
    setor: str | None
    moeda: str
    fonte_dados: str
