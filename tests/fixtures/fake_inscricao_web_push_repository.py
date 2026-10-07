from __future__ import annotations

from uuid import UUID

from app.domain.entities.inscricao_web_push import InscricaoWebPush
from app.repositories.interfaces.inscricao_web_push_repository import (
    InscricaoWebPushRepository,
)


class FakeInscricaoWebPushRepository(InscricaoWebPushRepository):
    def __init__(self) -> None:
        self._inscricoes: dict[UUID, InscricaoWebPush] = {}

    def buscar_por_endpoint(self, endpoint: str) -> InscricaoWebPush | None:
        return next((i for i in self._inscricoes.values() if i.endpoint == endpoint), None)

    def salvar(self, inscricao: InscricaoWebPush) -> None:
        self._inscricoes[inscricao.id] = inscricao

    def listar_por_usuario(self, usuario_id: UUID) -> list[InscricaoWebPush]:
        return [i for i in self._inscricoes.values() if i.usuario_id == usuario_id]

    def remover_por_endpoint(self, endpoint: str) -> None:
        inscricao = self.buscar_por_endpoint(endpoint)
        if inscricao is not None:
            del self._inscricoes[inscricao.id]

    def listar_todos(self) -> list[InscricaoWebPush]:
        return list(self._inscricoes.values())
