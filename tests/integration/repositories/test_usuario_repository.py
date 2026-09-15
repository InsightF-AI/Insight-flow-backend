from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.domain.entities.usuario import Usuario
from app.repositories.sqlalchemy.usuario_repository import SqlAlchemyUsuarioRepository

pytestmark = pytest.mark.integration


def _novo_usuario(email: str = "ana@example.com", senha: str = "segredo123") -> Usuario:
    return Usuario.criar(
        id=uuid4(),
        nome="Ana",
        email=email,
        senha=senha,
        criado_em=datetime(2026, 9, 8, 12, 0, 0, tzinfo=UTC),
    )


def test_salvar_e_buscar_por_id_retorna_o_mesmo_usuario(session):
    repo = SqlAlchemyUsuarioRepository(session)
    usuario = _novo_usuario()

    repo.salvar(usuario)
    encontrado = repo.buscar_por_id(usuario.id)

    assert encontrado is not None
    assert encontrado.email == usuario.email
    assert encontrado.criado_em == usuario.criado_em


def test_buscar_por_id_inexistente_retorna_none(session):
    repo = SqlAlchemyUsuarioRepository(session)

    assert repo.buscar_por_id(uuid4()) is None


def test_buscar_por_email_encontra_usuario_cadastrado(session):
    repo = SqlAlchemyUsuarioRepository(session)
    usuario = _novo_usuario(email="joao@example.com")
    repo.salvar(usuario)

    encontrado = repo.buscar_por_email("joao@example.com")

    assert encontrado is not None
    assert encontrado.id == usuario.id


def test_buscar_por_email_nao_encontrado_retorna_none(session):
    repo = SqlAlchemyUsuarioRepository(session)

    assert repo.buscar_por_email("naoexiste@example.com") is None


def test_usuario_reconstruido_do_banco_autentica_com_a_senha_original(session):
    repo = SqlAlchemyUsuarioRepository(session)
    usuario = _novo_usuario(senha="minhasenha")
    repo.salvar(usuario)

    encontrado = repo.buscar_por_email(usuario.email)

    assert encontrado.autenticar("minhasenha") is True


def test_salvar_usuario_existente_atualiza_os_dados(session):
    repo = SqlAlchemyUsuarioRepository(session)
    usuario = _novo_usuario()
    repo.salvar(usuario)

    usuario.nome = "Ana Atualizada"
    repo.salvar(usuario)

    encontrado = repo.buscar_por_id(usuario.id)
    assert encontrado.nome == "Ana Atualizada"


def test_salvar_dois_usuarios_com_mesmo_email_viola_constraint_unica(session):
    repo = SqlAlchemyUsuarioRepository(session)
    repo.salvar(_novo_usuario(email="duplicado@example.com"))

    with pytest.raises(IntegrityError):
        repo.salvar(_novo_usuario(email="duplicado@example.com"))
