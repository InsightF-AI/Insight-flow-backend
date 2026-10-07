from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models.inscricao_web_push import InscricaoWebPushModel
from app.domain.entities.inscricao_web_push import InscricaoWebPush
from app.repositories.interfaces.inscricao_web_push_repository import (
    InscricaoWebPushRepository,
)


class SqlAlchemyInscricaoWebPushRepository(InscricaoWebPushRepository):
    def __init__(self, session: Session):
        self._session = session

    def buscar_por_endpoint(self, endpoint: str) -> InscricaoWebPush | None:
        modelo = self._session.scalars(
            select(InscricaoWebPushModel).where(InscricaoWebPushModel.endpoint == endpoint)
        ).first()
        return self._para_entidade(modelo) if modelo is not None else None

    def salvar(self, inscricao: InscricaoWebPush) -> None:
        modelo = self._session.get(InscricaoWebPushModel, inscricao.id)
        if modelo is None:
            modelo = InscricaoWebPushModel(id=inscricao.id)
            self._session.add(modelo)
        modelo.usuario_id = inscricao.usuario_id
        modelo.endpoint = inscricao.endpoint
        modelo.p256dh = inscricao.p256dh
        modelo.auth = inscricao.auth
        modelo.criado_em = inscricao.criado_em
        modelo.atualizado_em = inscricao.atualizado_em
        self._session.commit()

    def listar_por_usuario(self, usuario_id: UUID) -> list[InscricaoWebPush]:
        modelos = self._session.scalars(
            select(InscricaoWebPushModel)
            .where(InscricaoWebPushModel.usuario_id == usuario_id)
            .order_by(InscricaoWebPushModel.criado_em)
        ).all()
        return [self._para_entidade(modelo) for modelo in modelos]

    def remover_por_endpoint(self, endpoint: str) -> None:
        self._session.execute(
            delete(InscricaoWebPushModel).where(InscricaoWebPushModel.endpoint == endpoint)
        )
        self._session.commit()

    @staticmethod
    def _para_entidade(modelo: InscricaoWebPushModel) -> InscricaoWebPush:
        return InscricaoWebPush(
            id=modelo.id,
            usuario_id=modelo.usuario_id,
            endpoint=modelo.endpoint,
            p256dh=modelo.p256dh,
            auth=modelo.auth,
            criado_em=modelo.criado_em,
            atualizado_em=modelo.atualizado_em,
        )
