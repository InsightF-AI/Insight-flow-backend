from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class DispositivoPush:
    id: UUID
    usuario_id: UUID
    token: str
    ativo: bool
    criado_em: datetime
    atualizado_em: datetime
