from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domain.entities.usuario import Usuario
from app.repositories.interfaces.usuario_repository import UsuarioRepository
from app.services.exceptions import CredenciaisInvalidasError, EmailJaCadastradoError


class UsuarioService:
    def __init__(self, repository: UsuarioRepository):
        self._repository = repository

    def cadastrar(self, nome: str, email: str, senha: str) -> Usuario:
        if self._repository.buscar_por_email(email) is not None:
            raise EmailJaCadastradoError(email)

        usuario = Usuario.criar(
            id=uuid4(),
            nome=nome,
            email=email,
            senha=senha,
            criado_em=datetime.now(UTC),
        )
        self._repository.salvar(usuario)
        return usuario

    def autenticar(self, email: str, senha: str) -> Usuario:
        usuario = self._repository.buscar_por_email(email)
        if usuario is None or not usuario.autenticar(senha):
            raise CredenciaisInvalidasError(email)
        return usuario

    def buscar_por_id(self, id: UUID) -> Usuario | None:
        return self._repository.buscar_por_id(id)
