from __future__ import annotations

from app.core.config import Settings
from app.integrations.expo.client import ExpoPushClient
from app.notifications.barramento import BarramentoNotificacoes
from app.notifications.canal import CanalNotificacao, CanalTempoReal
from app.notifications.canal_expo import CanalExpo
from app.repositories.interfaces.dispositivo_push_repository import DispositivoPushRepository
from app.repositories.interfaces.ticket_push_repository import TicketPushRepository


def montar_canais(
    settings: Settings,
    barramento: BarramentoNotificacoes,
    dispositivo_repository: DispositivoPushRepository,
    ticket_repository: TicketPushRepository,
    cliente_expo: ExpoPushClient,
) -> list[CanalNotificacao]:
    canais: list[CanalNotificacao] = [CanalTempoReal(barramento)]
    if settings.expo_push_habilitado:
        canais.append(CanalExpo(dispositivo_repository, ticket_repository, cliente_expo))
    return canais
