from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.domain.entities.refresh_token import RefreshToken
from app.domain.entities.usuario import Usuario
from app.repositories.sqlalchemy.refresh_token_repository import SqlAlchemyRefreshTokenRepository
from app.repositories.sqlalchemy.usuario_repository import SqlAlchemyUsuarioRepository

pytestmark = pytest.mark.integration

_AGORA = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)


def _novo_usuario(session) -> Usuario:
    usuario = Usuario.criar(
        id=uuid4(),
        nome="Ana",
        email=f"ana-{uuid4()}@example.com",
        senha="segredo123",
        criado_em=_AGORA,
    )
    SqlAlchemyUsuarioRepository(session).salvar(usuario)
    return usuario


def _token(usuario_id, familia_id, token_hash: str) -> RefreshToken:
    return RefreshToken(
        id=uuid4(),
        usuario_id=usuario_id,
        token_hash=token_hash,
        familia_id=familia_id,
        criado_em=_AGORA,
        expira_em=_AGORA + timedelta(days=30),
    )


def test_salvar_e_buscar_por_hash_devolve_datas_com_fuso(session):
    usuario = _novo_usuario(session)
    repositorio = SqlAlchemyRefreshTokenRepository(session)
    token = _token(usuario.id, uuid4(), "a" * 64)

    repositorio.salvar(token)
    encontrado = repositorio.buscar_por_hash("a" * 64)

    assert encontrado == token
    assert encontrado.expira_em.tzinfo is not None
    assert encontrado.esta_expirado(_AGORA) is False


def test_buscar_por_hash_inexistente_devolve_none(session):
    assert SqlAlchemyRefreshTokenRepository(session).buscar_por_hash("b" * 64) is None


def test_salvar_atualiza_a_revogacao(session):
    usuario = _novo_usuario(session)
    repositorio = SqlAlchemyRefreshTokenRepository(session)
    token = _token(usuario.id, uuid4(), "c" * 64)
    repositorio.salvar(token)

    token.revogar(_AGORA)
    repositorio.salvar(token)

    assert repositorio.buscar_por_hash("c" * 64).revogado_em == _AGORA


def test_revogar_familia_so_afeta_a_familia_informada(session):
    usuario = _novo_usuario(session)
    repositorio = SqlAlchemyRefreshTokenRepository(session)
    familia = uuid4()
    outra = uuid4()
    repositorio.salvar(_token(usuario.id, familia, "d" * 64))
    repositorio.salvar(_token(usuario.id, familia, "e" * 64))
    repositorio.salvar(_token(usuario.id, outra, "f" * 64))

    repositorio.revogar_familia(familia, _AGORA)

    assert repositorio.buscar_por_hash("d" * 64).esta_revogado() is True
    assert repositorio.buscar_por_hash("e" * 64).esta_revogado() is True
    assert repositorio.buscar_por_hash("f" * 64).esta_revogado() is False


def test_hash_duplicado_viola_restricao_unica(session):
    usuario = _novo_usuario(session)
    repositorio = SqlAlchemyRefreshTokenRepository(session)
    repositorio.salvar(_token(usuario.id, uuid4(), "9" * 64))

    with pytest.raises(IntegrityError):
        repositorio.salvar(_token(usuario.id, uuid4(), "9" * 64))


def test_revogar_se_ativo_so_revoga_uma_vez(session):
    usuario = _novo_usuario(session)
    repositorio = SqlAlchemyRefreshTokenRepository(session)
    token = _token(usuario.id, uuid4(), "7" * 64)
    repositorio.salvar(token)

    primeira = repositorio.revogar_se_ativo(token.id, _AGORA)
    segunda = repositorio.revogar_se_ativo(token.id, _AGORA + timedelta(minutes=1))

    assert primeira is True
    assert segunda is False
    assert repositorio.buscar_por_hash("7" * 64).revogado_em == _AGORA
