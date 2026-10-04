from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.domain.entities.refresh_token import RefreshToken
from app.repositories.interfaces.refresh_token_repository import RefreshTokenRepository


class FakeRefreshTokenRepository(RefreshTokenRepository):
    def __init__(self) -> None:
        self._tokens: dict[UUID, RefreshToken] = {}

    def salvar(self, token: RefreshToken) -> None:
        self._tokens[token.id] = token

    def buscar_por_hash(self, token_hash: str) -> RefreshToken | None:
        return next((t for t in self._tokens.values() if t.token_hash == token_hash), None)

    def revogar_se_ativo(self, token_id: UUID, revogado_em: datetime) -> bool:
        token = self._tokens.get(token_id)
        if token is None or token.esta_revogado():
            return False
        token.revogar(revogado_em)
        return True

    def revogar_familia(self, familia_id: UUID, revogado_em: datetime) -> None:
        for token in self._tokens.values():
            if token.familia_id == familia_id and not token.esta_revogado():
                token.revogar(revogado_em)

    def listar_todos(self) -> list[RefreshToken]:
        return list(self._tokens.values())
