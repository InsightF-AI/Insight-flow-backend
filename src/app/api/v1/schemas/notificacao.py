from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.domain.entities.notificacao import Notificacao
from app.domain.enums.tipo_notificacao import TipoNotificacao


class NotificacaoResponse(BaseModel):
    id: UUID
    ativo_id: UUID
    tipo: TipoNotificacao
    mensagem: str
    lida: bool
    criado_em: datetime

    @staticmethod
    def de(notificacao: Notificacao) -> "NotificacaoResponse":
        return NotificacaoResponse(
            id=notificacao.id,
            ativo_id=notificacao.ativo_id,
            tipo=notificacao.tipo,
            mensagem=notificacao.mensagem,
            lida=notificacao.lida,
            criado_em=notificacao.criado_em,
        )
