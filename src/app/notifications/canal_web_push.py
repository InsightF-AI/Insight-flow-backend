from __future__ import annotations

import logging

from app.domain.entities.notificacao import Notificacao
from app.integrations.web_push.client import (
    ResultadoWebPush,
    WebPushClient,
    WebPushIndisponivelError,
)
from app.notifications.canal import CanalNotificacao
from app.notifications.payload_push import payload_push
from app.repositories.interfaces.inscricao_web_push_repository import (
    InscricaoWebPushRepository,
)

logger = logging.getLogger(__name__)


class CanalWebPush(CanalNotificacao):
    def __init__(self, inscricao_repository: InscricaoWebPushRepository, cliente: WebPushClient):
        self._inscricao_repository = inscricao_repository
        self._cliente = cliente

    def entregar(self, notificacao: Notificacao) -> None:
        inscricoes = self._inscricao_repository.listar_por_usuario(notificacao.usuario_id)
        if not inscricoes:
            return

        payload = payload_push(notificacao)
        entregues = expiradas = falhas = 0
        for inscricao in inscricoes:
            try:
                resultado = self._cliente.enviar(
                    inscricao.endpoint, inscricao.p256dh, inscricao.auth, payload
                )
            except (WebPushIndisponivelError, ValueError) as exc:
                falhas += 1
                logger.warning(
                    "Falha ao enviar web push.",
                    extra={
                        "evento": "push_web_falhou",
                        "erro": str(exc),
                        "usuario_id": str(notificacao.usuario_id),
                    },
                )
                continue
            if resultado is ResultadoWebPush.ENTREGUE:
                entregues += 1
            elif resultado is ResultadoWebPush.INSCRICAO_EXPIRADA:
                self._inscricao_repository.remover_por_endpoint(inscricao.endpoint)
                expiradas += 1
            else:
                falhas += 1

        logger.info(
            "Web push enviado.",
            extra={
                "evento": "push_web_enviado",
                "usuario_id": str(notificacao.usuario_id),
                "notificacao_id": str(notificacao.id),
                "inscricoes": len(inscricoes),
                "entregues": entregues,
                "expiradas": expiradas,
                "falhas": falhas,
            },
        )
