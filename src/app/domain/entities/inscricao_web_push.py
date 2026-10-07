from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class InscricaoWebPush:
    id: UUID
    usuario_id: UUID
    endpoint: str
    p256dh: str
    auth: str
    criado_em: datetime
    atualizado_em: datetime
