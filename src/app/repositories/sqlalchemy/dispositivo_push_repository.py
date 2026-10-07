from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models.dispositivo_push import DispositivoPushModel
from app.domain.entities.dispositivo_push import DispositivoPush
from app.repositories.interfaces.dispositivo_push_repository import DispositivoPushRepository


class SqlAlchemyDispositivoPushRepository(DispositivoPushRepository):
    def __init__(self, session: Session):
        self._session = session

    def buscar_por_token(self, token: str) -> DispositivoPush | None:
        modelo = self._session.scalars(
            select(DispositivoPushModel).where(DispositivoPushModel.token == token)
        ).first()
        return self._para_entidade(modelo) if modelo is not None else None

    def salvar(self, dispositivo: DispositivoPush) -> None:
        modelo = self._session.get(DispositivoPushModel, dispositivo.id)
        if modelo is None:
            modelo = DispositivoPushModel(id=dispositivo.id)
            self._session.add(modelo)
        modelo.usuario_id = dispositivo.usuario_id
        modelo.token = dispositivo.token
        modelo.ativo = dispositivo.ativo
        modelo.criado_em = dispositivo.criado_em
        modelo.atualizado_em = dispositivo.atualizado_em
        self._session.commit()

    def listar_ativos_por_usuario(self, usuario_id: UUID) -> list[DispositivoPush]:
        modelos = self._session.scalars(
            select(DispositivoPushModel)
            .where(DispositivoPushModel.usuario_id == usuario_id, DispositivoPushModel.ativo)
            .order_by(DispositivoPushModel.criado_em)
        ).all()
        return [self._para_entidade(modelo) for modelo in modelos]

    def desativar_por_token(self, token: str, agora: datetime) -> None:
        self._session.execute(
            update(DispositivoPushModel)
            .where(DispositivoPushModel.token == token)
            .values(ativo=False, atualizado_em=agora)
        )
        self._session.commit()

    @staticmethod
    def _para_entidade(modelo: DispositivoPushModel) -> DispositivoPush:
        return DispositivoPush(
            id=modelo.id,
            usuario_id=modelo.usuario_id,
            token=modelo.token,
            ativo=modelo.ativo,
            criado_em=modelo.criado_em,
            atualizado_em=modelo.atualizado_em,
        )
