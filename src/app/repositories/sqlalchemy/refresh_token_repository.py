from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models.refresh_token import RefreshTokenModel
from app.domain.entities.refresh_token import RefreshToken
from app.repositories.interfaces.refresh_token_repository import RefreshTokenRepository


class SqlAlchemyRefreshTokenRepository(RefreshTokenRepository):
    def __init__(self, session: Session):
        self._session = session

    def salvar(self, token: RefreshToken) -> None:
        modelo = self._session.get(RefreshTokenModel, token.id)
        if modelo is None:
            modelo = RefreshTokenModel(id=token.id)
            self._session.add(modelo)
        modelo.usuario_id = token.usuario_id
        modelo.token_hash = token.token_hash
        modelo.familia_id = token.familia_id
        modelo.criado_em = token.criado_em
        modelo.expira_em = token.expira_em
        modelo.revogado_em = token.revogado_em
        self._session.commit()

    def buscar_por_hash(self, token_hash: str) -> RefreshToken | None:
        modelo = self._session.scalars(
            select(RefreshTokenModel).where(RefreshTokenModel.token_hash == token_hash)
        ).first()
        return self._para_entidade(modelo) if modelo is not None else None

    def revogar_se_ativo(self, token_id: UUID, revogado_em: datetime) -> bool:
        resultado = self._session.execute(
            update(RefreshTokenModel)
            .where(RefreshTokenModel.id == token_id, RefreshTokenModel.revogado_em.is_(None))
            .values(revogado_em=revogado_em)
        )
        self._session.commit()
        return resultado.rowcount == 1

    def revogar_familia(self, familia_id: UUID, revogado_em: datetime) -> None:
        self._session.execute(
            update(RefreshTokenModel)
            .where(
                RefreshTokenModel.familia_id == familia_id,
                RefreshTokenModel.revogado_em.is_(None),
            )
            .values(revogado_em=revogado_em)
        )
        self._session.commit()

    @staticmethod
    def _para_entidade(modelo: RefreshTokenModel) -> RefreshToken:
        return RefreshToken(
            id=modelo.id,
            usuario_id=modelo.usuario_id,
            token_hash=modelo.token_hash,
            familia_id=modelo.familia_id,
            criado_em=modelo.criado_em,
            expira_em=modelo.expira_em,
            revogado_em=modelo.revogado_em,
        )
