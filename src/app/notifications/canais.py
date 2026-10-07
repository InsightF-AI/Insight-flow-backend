from __future__ import annotations

from app.core.config import Settings
from app.integrations.expo.client import ExpoPushClient
from app.integrations.web_push.client import WebPushClient
from app.notifications.barramento import BarramentoNotificacoes
from app.notifications.canal import CanalNotificacao, CanalTempoReal
from app.notifications.canal_expo import CanalExpo
from app.notifications.canal_web_push import CanalWebPush
from app.repositories.interfaces.dispositivo_push_repository import DispositivoPushRepository
from app.repositories.interfaces.inscricao_web_push_repository import (
    InscricaoWebPushRepository,
)
from app.repositories.interfaces.ticket_push_repository import TicketPushRepository


def montar_canais(
    settings: Settings,
    barramento: BarramentoNotificacoes,
    dispositivo_repository: DispositivoPushRepository,
    ticket_repository: TicketPushRepository,
    cliente_expo: ExpoPushClient,
    inscricao_repository: InscricaoWebPushRepository,
    cliente_web_push: WebPushClient | None,
) -> list[CanalNotificacao]:
    canais: list[CanalNotificacao] = [CanalTempoReal(barramento)]
    if settings.expo_push_habilitado:
        canais.append(CanalExpo(dispositivo_repository, ticket_repository, cliente_expo))
    if cliente_web_push is not None:
        canais.append(CanalWebPush(inscricao_repository, cliente_web_push))
    return canais
