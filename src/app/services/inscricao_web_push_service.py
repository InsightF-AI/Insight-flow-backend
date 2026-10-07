from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domain.entities.inscricao_web_push import InscricaoWebPush
from app.integrations.web_push.validacao import validar_inscricao
from app.repositories.interfaces.inscricao_web_push_repository import (
    InscricaoWebPushRepository,
)

logger = logging.getLogger(__name__)


class InscricaoWebPushService:
    def __init__(
        self,
        inscricao_repository: InscricaoWebPushRepository,
        hosts_permitidos: list[str],
        agora: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self._inscricao_repository = inscricao_repository
        self._hosts_permitidos = hosts_permitidos
        self._agora = agora

    def registrar(self, usuario_id: UUID, endpoint: str, p256dh: str, auth: str) -> bool:
        validar_inscricao(endpoint, p256dh, auth, self._hosts_permitidos)
        agora = self._agora()
        existente = self._inscricao_repository.buscar_por_endpoint(endpoint)
        if existente is None:
            self._inscricao_repository.salvar(
                InscricaoWebPush(
                    id=uuid4(),
                    usuario_id=usuario_id,
                    endpoint=endpoint,
                    p256dh=p256dh,
                    auth=auth,
                    criado_em=agora,
                    atualizado_em=agora,
                )
            )
            self._logar_registro(usuario_id, transferida=False)
            return True

        transferida = existente.usuario_id != usuario_id
        existente.usuario_id = usuario_id
        existente.p256dh = p256dh
        existente.auth = auth
        existente.atualizado_em = agora
        self._inscricao_repository.salvar(existente)
        self._logar_registro(usuario_id, transferida=transferida)
        return False

    def remover(self, usuario_id: UUID, endpoint: str) -> None:
        existente = self._inscricao_repository.buscar_por_endpoint(endpoint)
        if existente is None or existente.usuario_id != usuario_id:
            return
        self._inscricao_repository.remover_por_endpoint(endpoint)

    @staticmethod
    def _logar_registro(usuario_id: UUID, transferida: bool) -> None:
        logger.info(
            "Inscricao de web push registrada.",
            extra={
                "evento": "inscricao_web_push_registrada",
                "usuario_id": str(usuario_id),
                "transferida": transferida,
            },
        )
