from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from jose import JWTError, jwt

_ALGORITHM = "HS256"
_TIPO_REDEFINICAO = "redefinir_senha"


class TokenInvalidoError(Exception):
    pass


def criar_token(usuario_id: UUID, secret_key: str, expiracao_minutos: int) -> str:
    expira_em = datetime.now(UTC) + timedelta(minutes=expiracao_minutos)
    payload = {"sub": str(usuario_id), "exp": expira_em}
    return jwt.encode(payload, secret_key, algorithm=_ALGORITHM)


def decodificar_token(token: str, secret_key: str) -> UUID:
    try:
        payload = jwt.decode(token, secret_key, algorithms=[_ALGORITHM])
        if "tipo" in payload:
            raise TokenInvalidoError
        return UUID(payload["sub"])
    except (JWTError, KeyError, ValueError) as exc:
        raise TokenInvalidoError from exc


def criar_token_redefinicao(
    usuario_id: UUID, impressao_senha: str, secret_key: str, expiracao_minutos: int
) -> str:
    expira_em = datetime.now(UTC) + timedelta(minutes=expiracao_minutos)
    payload = {
        "sub": str(usuario_id),
        "exp": expira_em,
        "tipo": _TIPO_REDEFINICAO,
        "fp": impressao_senha,
    }
    return jwt.encode(payload, secret_key, algorithm=_ALGORITHM)


def decodificar_token_redefinicao(token: str, secret_key: str) -> tuple[UUID, str]:
    try:
        payload = jwt.decode(token, secret_key, algorithms=[_ALGORITHM])
        if payload.get("tipo") != _TIPO_REDEFINICAO:
            raise TokenInvalidoError
        return UUID(payload["sub"]), str(payload["fp"])
    except (JWTError, KeyError, ValueError) as exc:
        raise TokenInvalidoError from exc


def decodificar_token_com_expiracao(token: str, secret_key: str) -> tuple[UUID, datetime]:
    try:
        payload = jwt.decode(token, secret_key, algorithms=[_ALGORITHM])
        if "tipo" in payload:
            raise TokenInvalidoError
        return UUID(payload["sub"]), datetime.fromtimestamp(payload["exp"], tz=UTC)
    except (JWTError, KeyError, ValueError, TypeError) as exc:
        raise TokenInvalidoError from exc
