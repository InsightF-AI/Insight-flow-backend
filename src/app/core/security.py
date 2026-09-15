from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from jose import JWTError, jwt

_ALGORITHM = "HS256"


class TokenInvalidoError(Exception):
    pass


def criar_token(usuario_id: UUID, secret_key: str, expiracao_minutos: int) -> str:
    expira_em = datetime.now(UTC) + timedelta(minutes=expiracao_minutos)
    payload = {"sub": str(usuario_id), "exp": expira_em}
    return jwt.encode(payload, secret_key, algorithm=_ALGORITHM)


def decodificar_token(token: str, secret_key: str) -> UUID:
    try:
        payload = jwt.decode(token, secret_key, algorithms=[_ALGORITHM])
        return UUID(payload["sub"])
    except (JWTError, KeyError, ValueError) as exc:
        raise TokenInvalidoError from exc
