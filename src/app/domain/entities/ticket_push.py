from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class TicketPush:
    id: str
    token: str
    criado_em: datetime
