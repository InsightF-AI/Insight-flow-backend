from __future__ import annotations

from uuid import UUID

from app.domain.entities.notificacao import Notificacao
from app.repositories.interfaces.notificacao_repository import NotificacaoRepository


class FakeNotificacaoRepository(NotificacaoRepository):
    def __init__(self) -> None:
        self._notificacoes: dict[UUID, Notificacao] = {}

    def salvar(self, notificacao: Notificacao) -> None:
        self._notificacoes[notificacao.id] = notificacao

    def buscar_por_id(self, notificacao_id: UUID) -> Notificacao | None:
        return self._notificacoes.get(notificacao_id)

    def listar_por_usuario(
        self, usuario_id: UUID, apenas_nao_lidas: bool = False
    ) -> list[Notificacao]:
        notificacoes = [
            notificacao
            for notificacao in self._notificacoes.values()
            if notificacao.usuario_id == usuario_id
        ]
        if apenas_nao_lidas:
            notificacoes = [n for n in notificacoes if not n.lida]
        return notificacoes
