from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class Sinal:
    id: UUID
    ativo_id: UUID
    regra_id: UUID
    data_ativacao: datetime
    contexto: dict
    data_desativacao: datetime | None = None
