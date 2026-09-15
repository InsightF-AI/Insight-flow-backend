from __future__ import annotations

from uuid import UUID

from app.domain.entities.usuario import Usuario
from app.repositories.interfaces.usuario_repository import UsuarioRepository


class FakeUsuarioRepository(UsuarioRepository):
    def __init__(self) -> None:
        self._usuarios: dict[UUID, Usuario] = {}

    def salvar(self, usuario: Usuario) -> None:
        self._usuarios[usuario.id] = usuario

    def buscar_por_id(self, id: UUID) -> Usuario | None:
        return self._usuarios.get(id)

    def buscar_por_email(self, email: str) -> Usuario | None:
        for usuario in self._usuarios.values():
            if usuario.email == email:
                return usuario
        return None
