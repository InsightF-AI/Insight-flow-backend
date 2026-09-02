from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["bcrypt"], bcrypt__rounds=12)


@dataclass
class Usuario:
    id: UUID
    nome: str
    email: str
    senha_hash: str
    criado_em: datetime
    ativo: bool = True

    @staticmethod
    def criar(id: UUID, nome: str, email: str, senha: str, criado_em: datetime) -> Usuario:
        return Usuario(
            id=id,
            nome=nome,
            email=email,
            senha_hash=_pwd_context.hash(senha),
            criado_em=criado_em,
        )

    def autenticar(self, senha: str) -> bool:
        return _pwd_context.verify(senha, self.senha_hash)

    def alterar_senha(self, nova_senha: str) -> None:
        self.senha_hash = _pwd_context.hash(nova_senha)
