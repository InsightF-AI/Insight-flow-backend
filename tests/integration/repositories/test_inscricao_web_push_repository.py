from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.domain.entities.inscricao_web_push import InscricaoWebPush
from app.domain.entities.usuario import Usuario
from app.repositories.sqlalchemy.inscricao_web_push_repository import (
    SqlAlchemyInscricaoWebPushRepository,
)
from app.repositories.sqlalchemy.usuario_repository import SqlAlchemyUsuarioRepository

pytestmark = pytest.mark.integration

_AGORA = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
_ENDPOINT = "https://fcm.googleapis.com/fcm/send/abc"


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


def _inscricao(usuario_id, endpoint: str = _ENDPOINT) -> InscricaoWebPush:
    return InscricaoWebPush(
        id=uuid4(),
        usuario_id=usuario_id,
        endpoint=endpoint,
        p256dh="chave",
        auth="segredo",
        criado_em=_AGORA,
        atualizado_em=_AGORA,
    )


def test_salvar_e_buscar_por_endpoint(session):
    usuario = _novo_usuario(session)
    repositorio = SqlAlchemyInscricaoWebPushRepository(session)
    inscricao = _inscricao(usuario.id)

    repositorio.salvar(inscricao)

    assert repositorio.buscar_por_endpoint(_ENDPOINT) == inscricao


def test_buscar_endpoint_inexistente_devolve_none(session):
    assert SqlAlchemyInscricaoWebPushRepository(session).buscar_por_endpoint("x") is None


def test_salvar_atualiza_dono_e_chaves(session):
    primeiro = _novo_usuario(session)
    segundo = _novo_usuario(session)
    repositorio = SqlAlchemyInscricaoWebPushRepository(session)
    inscricao = _inscricao(primeiro.id)
    repositorio.salvar(inscricao)

    inscricao.usuario_id = segundo.id
    inscricao.p256dh = "nova-chave"
    inscricao.atualizado_em = _AGORA + timedelta(hours=1)
    repositorio.salvar(inscricao)

    encontrada = repositorio.buscar_por_endpoint(_ENDPOINT)
    assert encontrada.usuario_id == segundo.id
    assert encontrada.p256dh == "nova-chave"


def test_listar_por_usuario(session):
    usuario = _novo_usuario(session)
    outro = _novo_usuario(session)
    repositorio = SqlAlchemyInscricaoWebPushRepository(session)
    repositorio.salvar(_inscricao(usuario.id, "https://fcm.googleapis.com/fcm/send/1"))
    repositorio.salvar(_inscricao(usuario.id, "https://fcm.googleapis.com/fcm/send/2"))
    repositorio.salvar(_inscricao(outro.id, "https://fcm.googleapis.com/fcm/send/3"))

    endpoints = sorted(i.endpoint for i in repositorio.listar_por_usuario(usuario.id))

    assert endpoints == [
        "https://fcm.googleapis.com/fcm/send/1",
        "https://fcm.googleapis.com/fcm/send/2",
    ]


def test_remover_por_endpoint(session):
    usuario = _novo_usuario(session)
    repositorio = SqlAlchemyInscricaoWebPushRepository(session)
    repositorio.salvar(_inscricao(usuario.id))

    repositorio.remover_por_endpoint(_ENDPOINT)

    assert repositorio.buscar_por_endpoint(_ENDPOINT) is None


def test_remover_endpoint_inexistente_nao_lanca_erro(session):
    SqlAlchemyInscricaoWebPushRepository(session).remover_por_endpoint("nada")
