from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.enums.tipo_notificacao import TipoNotificacao


@dataclass
class Notificacao:
    id: UUID
    usuario_id: UUID
    ativo_id: UUID
    tipo: TipoNotificacao
    mensagem: str
    contexto: dict
    criado_em: datetime
    lida: bool = False
