from __future__ import annotations

import hashlib
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.core.security import criar_token
from app.domain.entities.refresh_token import RefreshToken
from app.repositories.interfaces.refresh_token_repository import RefreshTokenRepository
from app.repositories.interfaces.usuario_repository import UsuarioRepository
from app.services.exceptions import RefreshTokenInvalidoError


@dataclass
class ParTokens:
    access_token: str
    refresh_token: str
    expires_in: int


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class RefreshTokenService:
    def __init__(
        self,
        refresh_token_repository: RefreshTokenRepository,
        usuario_repository: UsuarioRepository,
        jwt_secret_key: str,
        access_expiracao_minutos: int,
        refresh_expiracao_dias: int,
        agora: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self._refresh_token_repository = refresh_token_repository
        self._usuario_repository = usuario_repository
        self._jwt_secret_key = jwt_secret_key
        self._access_expiracao_minutos = access_expiracao_minutos
        self._refresh_expiracao_dias = refresh_expiracao_dias
        self._agora = agora

    def emitir(self, usuario_id: UUID) -> ParTokens:
        return self._emitir_na_familia(usuario_id, uuid4())

    def renovar(self, refresh_token: str) -> ParTokens:
        agora = self._agora()
        token = self._refresh_token_repository.buscar_por_hash(_hash(refresh_token))
        if token is None:
            raise RefreshTokenInvalidoError
        if token.esta_revogado():
            self._refresh_token_repository.revogar_familia(token.familia_id, agora)
            raise RefreshTokenInvalidoError
        if token.esta_expirado(agora):
            raise RefreshTokenInvalidoError
        usuario = self._usuario_repository.buscar_por_id(token.usuario_id)
        if usuario is None or not usuario.ativo:
            raise RefreshTokenInvalidoError

        if not self._refresh_token_repository.revogar_se_ativo(token.id, agora):
            self._refresh_token_repository.revogar_familia(token.familia_id, agora)
            raise RefreshTokenInvalidoError
        return self._emitir_na_familia(token.usuario_id, token.familia_id)

    def revogar(self, refresh_token: str) -> None:
        token = self._refresh_token_repository.buscar_por_hash(_hash(refresh_token))
        if token is not None:
            self._refresh_token_repository.revogar_familia(token.familia_id, self._agora())

    def _emitir_na_familia(self, usuario_id: UUID, familia_id: UUID) -> ParTokens:
        agora = self._agora()
        refresh_token = secrets.token_urlsafe(48)
        self._refresh_token_repository.salvar(
            RefreshToken(
                id=uuid4(),
                usuario_id=usuario_id,
                token_hash=_hash(refresh_token),
                familia_id=familia_id,
                criado_em=agora,
                expira_em=agora + timedelta(days=self._refresh_expiracao_dias),
            )
        )
        return ParTokens(
            access_token=criar_token(
                usuario_id, self._jwt_secret_key, self._access_expiracao_minutos
            ),
            refresh_token=refresh_token,
            expires_in=self._access_expiracao_minutos * 60,
        )
