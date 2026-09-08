from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.usuario import UsuarioModel
from app.domain.entities.usuario import Usuario
from app.repositories.interfaces.usuario_repository import UsuarioRepository


class SqlAlchemyUsuarioRepository(UsuarioRepository):
    def __init__(self, session: Session):
        self._session = session

    def salvar(self, usuario: Usuario) -> None:
        modelo = self._session.get(UsuarioModel, usuario.id)
        if modelo is None:
            modelo = UsuarioModel(id=usuario.id)
            self._session.add(modelo)

        modelo.nome = usuario.nome
        modelo.email = usuario.email
        modelo.senha_hash = usuario.senha_hash
        modelo.criado_em = usuario.criado_em
        modelo.ativo = usuario.ativo
        self._session.commit()

    def buscar_por_id(self, id: UUID) -> Usuario | None:
        modelo = self._session.get(UsuarioModel, id)
        return self._para_entidade(modelo) if modelo is not None else None

    def buscar_por_email(self, email: str) -> Usuario | None:
        modelo = self._session.scalar(select(UsuarioModel).where(UsuarioModel.email == email))
        return self._para_entidade(modelo) if modelo is not None else None

    @staticmethod
    def _para_entidade(modelo: UsuarioModel) -> Usuario:
        return Usuario(
            id=modelo.id,
            nome=modelo.nome,
            email=modelo.email,
            senha_hash=modelo.senha_hash,
            criado_em=modelo.criado_em,
            ativo=modelo.ativo,
        )
