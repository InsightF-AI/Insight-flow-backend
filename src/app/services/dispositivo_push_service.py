from __future__ import annotations

import logging
import re
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domain.entities.dispositivo_push import DispositivoPush
from app.repositories.interfaces.dispositivo_push_repository import DispositivoPushRepository
from app.services.exceptions import TokenPushInvalidoError

logger = logging.getLogger(__name__)

_FORMATO_TOKEN = re.compile(r"^(ExponentPushToken|ExpoPushToken)\[[^\]]+\]$")
_TAMANHO_MAXIMO_TOKEN = 255


def _normalizar(token: str) -> str:
    normalizado = token.strip()
    if len(normalizado) > _TAMANHO_MAXIMO_TOKEN or not _FORMATO_TOKEN.fullmatch(normalizado):
        raise TokenPushInvalidoError
    return normalizado


class DispositivoPushService:
    def __init__(
        self,
        dispositivo_repository: DispositivoPushRepository,
        agora: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self._dispositivo_repository = dispositivo_repository
        self._agora = agora

    def registrar(self, usuario_id: UUID, token: str) -> bool:
        token = _normalizar(token)
        agora = self._agora()
        existente = self._dispositivo_repository.buscar_por_token(token)
        if existente is None:
            self._dispositivo_repository.salvar(
                DispositivoPush(
                    id=uuid4(),
                    usuario_id=usuario_id,
                    token=token,
                    ativo=True,
                    criado_em=agora,
                    atualizado_em=agora,
                )
            )
            self._logar_registro(usuario_id, transferido=False)
            return True

        transferido = existente.usuario_id != usuario_id
        existente.usuario_id = usuario_id
        existente.ativo = True
        existente.atualizado_em = agora
        self._dispositivo_repository.salvar(existente)
        self._logar_registro(usuario_id, transferido=transferido)
        return False

    def remover(self, usuario_id: UUID, token: str) -> None:
        existente = self._dispositivo_repository.buscar_por_token(token.strip())
        if existente is None or existente.usuario_id != usuario_id:
            return
        self._dispositivo_repository.desativar_por_token(existente.token, self._agora())

    @staticmethod
    def _logar_registro(usuario_id: UUID, transferido: bool) -> None:
        logger.info(
            "Dispositivo de push registrado.",
            extra={
                "evento": "dispositivo_registrado",
                "usuario_id": str(usuario_id),
                "transferido": transferido,
            },
        )
