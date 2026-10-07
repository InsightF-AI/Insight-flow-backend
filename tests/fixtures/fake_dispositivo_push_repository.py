from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.domain.entities.dispositivo_push import DispositivoPush
from app.repositories.interfaces.dispositivo_push_repository import DispositivoPushRepository


class FakeDispositivoPushRepository(DispositivoPushRepository):
    def __init__(self) -> None:
        self._dispositivos: dict[UUID, DispositivoPush] = {}

    def buscar_por_token(self, token: str) -> DispositivoPush | None:
        return next((d for d in self._dispositivos.values() if d.token == token), None)

    def salvar(self, dispositivo: DispositivoPush) -> None:
        self._dispositivos[dispositivo.id] = dispositivo

    def listar_ativos_por_usuario(self, usuario_id: UUID) -> list[DispositivoPush]:
        return [d for d in self._dispositivos.values() if d.usuario_id == usuario_id and d.ativo]

    def desativar_por_token(self, token: str, agora: datetime) -> None:
        dispositivo = self.buscar_por_token(token)
        if dispositivo is not None:
            dispositivo.ativo = False
            dispositivo.atualizado_em = agora

    def listar_todos(self) -> list[DispositivoPush]:
        return list(self._dispositivos.values())
