from __future__ import annotations

import logging
from datetime import datetime, timedelta

from app.integrations.expo.client import TOKEN_NAO_REGISTRADO, ExpoPushClient
from app.repositories.interfaces.dispositivo_push_repository import DispositivoPushRepository
from app.repositories.interfaces.ticket_push_repository import TicketPushRepository

logger = logging.getLogger(__name__)

_ESPERA_MINIMA = timedelta(minutes=15)
_VALIDADE_RECIBO = timedelta(hours=24)
_CREDENCIAIS_INVALIDAS = "InvalidCredentials"


def conferir_recibos_push(
    ticket_repository: TicketPushRepository,
    dispositivo_repository: DispositivoPushRepository,
    cliente: ExpoPushClient,
    agora: datetime,
    lote: int = 1000,
) -> None:
    verificados = 0
    desativados = 0
    pendentes = 0
    limite = agora - _ESPERA_MINIMA

    while True:
        tickets = ticket_repository.listar_anteriores_a(limite, lote)
        if not tickets:
            break

        recibos = cliente.buscar_recibos([ticket.id for ticket in tickets])
        remover: list[str] = []
        pendentes = 0
        for ticket in tickets:
            recibo = recibos.get(ticket.id)
            if recibo is None:
                if agora - ticket.criado_em >= _VALIDADE_RECIBO:
                    remover.append(ticket.id)
                else:
                    pendentes += 1
                continue

            verificados += 1
            remover.append(ticket.id)
            if recibo.status == "ok":
                continue
            if recibo.erro == TOKEN_NAO_REGISTRADO:
                dispositivo_repository.desativar_por_token(ticket.token, agora)
                desativados += 1
            elif recibo.erro == _CREDENCIAIS_INVALIDAS:
                logger.error(
                    "Expo recusou as credenciais de push do projeto.",
                    extra={"evento": "recibo_push_com_erro", "erro": recibo.erro},
                )
            else:
                logger.warning(
                    "Recibo de push com erro.",
                    extra={"evento": "recibo_push_com_erro", "erro": recibo.erro},
                )

        if remover:
            ticket_repository.remover_muitos(remover)
        if not remover or len(tickets) < lote:
            break

    logger.info(
        "Recibos de push conferidos.",
        extra={
            "evento": "recibos_push_conferidos",
            "verificados": verificados,
            "tokens_desativados": desativados,
            "pendentes": pendentes,
        },
    )
