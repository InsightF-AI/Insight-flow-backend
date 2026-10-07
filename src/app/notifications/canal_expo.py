from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime

from app.domain.entities.notificacao import Notificacao
from app.domain.entities.ticket_push import TicketPush
from app.domain.enums.tipo_notificacao import TipoNotificacao
from app.integrations.expo.client import TOKEN_NAO_REGISTRADO, ExpoPushClient
from app.notifications.canal import CanalNotificacao
from app.repositories.interfaces.dispositivo_push_repository import DispositivoPushRepository
from app.repositories.interfaces.ticket_push_repository import TicketPushRepository

logger = logging.getLogger(__name__)

_TITULOS = {
    TipoNotificacao.SINAL_ATIVADO: "Sinal técnico",
    TipoNotificacao.ALERTA_DISPARADO: "Alerta de preço",
    TipoNotificacao.RESUMO_DIARIO: "Resumo diário",
}


def _mensagem(token: str, notificacao: Notificacao) -> dict:
    return {
        "to": token,
        "title": _TITULOS.get(notificacao.tipo, "InsightFlow"),
        "body": notificacao.mensagem,
        "data": {
            "notificacao_id": str(notificacao.id),
            "tipo": notificacao.tipo.value,
            "ativo_id": str(notificacao.ativo_id) if notificacao.ativo_id else None,
        },
        "sound": "default",
        "priority": "high",
    }


class CanalExpo(CanalNotificacao):
    def __init__(
        self,
        dispositivo_repository: DispositivoPushRepository,
        ticket_repository: TicketPushRepository,
        cliente: ExpoPushClient,
        agora: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self._dispositivo_repository = dispositivo_repository
        self._ticket_repository = ticket_repository
        self._cliente = cliente
        self._agora = agora

    def entregar(self, notificacao: Notificacao) -> None:
        dispositivos = self._dispositivo_repository.listar_ativos_por_usuario(
            notificacao.usuario_id
        )
        if not dispositivos:
            return

        resultados = self._cliente.enviar(
            [_mensagem(dispositivo.token, notificacao) for dispositivo in dispositivos]
        )
        agora = self._agora()
        tickets: list[TicketPush] = []
        erros = 0
        for resultado in resultados:
            if resultado.ticket_id is not None:
                tickets.append(
                    TicketPush(id=resultado.ticket_id, token=resultado.token, criado_em=agora)
                )
                continue
            erros += 1
            if resultado.erro == TOKEN_NAO_REGISTRADO:
                self._dispositivo_repository.desativar_por_token(resultado.token, agora)
            else:
                logger.warning(
                    "Push recusado pela Expo.",
                    extra={
                        "evento": "push_recusado",
                        "erro": resultado.erro,
                        "usuario_id": str(notificacao.usuario_id),
                    },
                )

        if tickets:
            self._ticket_repository.salvar_muitos(tickets)
        logger.info(
            "Push enviado.",
            extra={
                "evento": "push_enviado",
                "usuario_id": str(notificacao.usuario_id),
                "notificacao_id": str(notificacao.id),
                "dispositivos": len(dispositivos),
                "erros": erros,
            },
        )
