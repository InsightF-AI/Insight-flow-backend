from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.notificacao import NotificacaoModel
from app.domain.entities.notificacao import Notificacao
from app.domain.enums.tipo_notificacao import TipoNotificacao
from app.repositories.interfaces.notificacao_repository import NotificacaoRepository


class SqlAlchemyNotificacaoRepository(NotificacaoRepository):
    def __init__(self, session: Session):
        self._session = session

    def salvar(self, notificacao: Notificacao) -> None:
        modelo = self._session.get(NotificacaoModel, notificacao.id)
        if modelo is None:
            modelo = NotificacaoModel(id=notificacao.id)
            self._session.add(modelo)

        modelo.usuario_id = notificacao.usuario_id
        modelo.ativo_id = notificacao.ativo_id
        modelo.tipo = notificacao.tipo
        modelo.mensagem = notificacao.mensagem
        modelo.contexto = notificacao.contexto
        modelo.lida = notificacao.lida
        modelo.criado_em = notificacao.criado_em
        self._session.commit()

    def buscar_por_id(self, notificacao_id: UUID) -> Notificacao | None:
        modelo = self._session.get(NotificacaoModel, notificacao_id)
        return self._para_entidade(modelo) if modelo is not None else None

    def listar_por_usuario(
        self, usuario_id: UUID, apenas_nao_lidas: bool = False
    ) -> list[Notificacao]:
        filtros = [NotificacaoModel.usuario_id == usuario_id]
        if apenas_nao_lidas:
            filtros.append(NotificacaoModel.lida.is_(False))
        modelos = self._session.scalars(
            select(NotificacaoModel).where(*filtros).order_by(NotificacaoModel.criado_em.desc())
        )
        return [self._para_entidade(modelo) for modelo in modelos]

    @staticmethod
    def _para_entidade(modelo: NotificacaoModel) -> Notificacao:
        return Notificacao(
            id=modelo.id,
            usuario_id=modelo.usuario_id,
            ativo_id=modelo.ativo_id,
            tipo=TipoNotificacao(modelo.tipo),
            mensagem=modelo.mensagem,
            contexto=modelo.contexto,
            lida=modelo.lida,
            criado_em=modelo.criado_em,
        )
