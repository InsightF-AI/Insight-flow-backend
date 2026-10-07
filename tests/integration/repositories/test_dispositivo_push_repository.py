from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.domain.entities.dispositivo_push import DispositivoPush
from app.domain.entities.usuario import Usuario
from app.repositories.sqlalchemy.dispositivo_push_repository import (
    SqlAlchemyDispositivoPushRepository,
)
from app.repositories.sqlalchemy.usuario_repository import SqlAlchemyUsuarioRepository

pytestmark = pytest.mark.integration

_AGORA = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)


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


def _dispositivo(usuario_id, token: str, ativo: bool = True) -> DispositivoPush:
    return DispositivoPush(
        id=uuid4(),
        usuario_id=usuario_id,
        token=token,
        ativo=ativo,
        criado_em=_AGORA,
        atualizado_em=_AGORA,
    )


def test_salvar_e_buscar_por_token(session):
    usuario = _novo_usuario(session)
    repositorio = SqlAlchemyDispositivoPushRepository(session)
    dispositivo = _dispositivo(usuario.id, "ExponentPushToken[a]")

    repositorio.salvar(dispositivo)

    assert repositorio.buscar_por_token("ExponentPushToken[a]") == dispositivo


def test_buscar_por_token_inexistente_devolve_none(session):
    assert SqlAlchemyDispositivoPushRepository(session).buscar_por_token("x") is None


def test_salvar_atualiza_usuario_e_estado_do_mesmo_registro(session):
    primeiro = _novo_usuario(session)
    segundo = _novo_usuario(session)
    repositorio = SqlAlchemyDispositivoPushRepository(session)
    dispositivo = _dispositivo(primeiro.id, "ExponentPushToken[b]", ativo=False)
    repositorio.salvar(dispositivo)

    dispositivo.usuario_id = segundo.id
    dispositivo.ativo = True
    dispositivo.atualizado_em = _AGORA + timedelta(hours=1)
    repositorio.salvar(dispositivo)

    encontrado = repositorio.buscar_por_token("ExponentPushToken[b]")
    assert encontrado.usuario_id == segundo.id
    assert encontrado.ativo is True
    assert encontrado.atualizado_em == _AGORA + timedelta(hours=1)


def test_listar_ativos_por_usuario_ignora_inativos_e_outros_usuarios(session):
    usuario = _novo_usuario(session)
    outro = _novo_usuario(session)
    repositorio = SqlAlchemyDispositivoPushRepository(session)
    repositorio.salvar(_dispositivo(usuario.id, "ExponentPushToken[c1]"))
    repositorio.salvar(_dispositivo(usuario.id, "ExponentPushToken[c2]", ativo=False))
    repositorio.salvar(_dispositivo(outro.id, "ExponentPushToken[c3]"))

    tokens = [d.token for d in repositorio.listar_ativos_por_usuario(usuario.id)]

    assert tokens == ["ExponentPushToken[c1]"]


def test_desativar_por_token(session):
    usuario = _novo_usuario(session)
    repositorio = SqlAlchemyDispositivoPushRepository(session)
    repositorio.salvar(_dispositivo(usuario.id, "ExponentPushToken[d]"))

    repositorio.desativar_por_token("ExponentPushToken[d]", _AGORA + timedelta(minutes=5))

    encontrado = repositorio.buscar_por_token("ExponentPushToken[d]")
    assert encontrado.ativo is False
    assert encontrado.atualizado_em == _AGORA + timedelta(minutes=5)


def test_desativar_token_inexistente_nao_lanca_erro(session):
    SqlAlchemyDispositivoPushRepository(session).desativar_por_token("nada", _AGORA)
