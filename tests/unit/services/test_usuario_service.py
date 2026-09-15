from uuid import uuid4

import pytest

from app.services.exceptions import CredenciaisInvalidasError, EmailJaCadastradoError
from app.services.usuario_service import UsuarioService
from tests.fixtures.fake_usuario_repository import FakeUsuarioRepository


def _service() -> UsuarioService:
    return UsuarioService(FakeUsuarioRepository())


def test_cadastrar_persiste_usuario_com_senha_hasheada():
    service = _service()

    usuario = service.cadastrar(nome="Ana", email="ana@example.com", senha="segredo123")

    assert usuario.nome == "Ana"
    assert usuario.email == "ana@example.com"
    assert usuario.senha_hash != "segredo123"
    assert usuario.autenticar("segredo123") is True


def test_cadastrar_com_email_ja_cadastrado_lanca_erro():
    service = _service()
    service.cadastrar(nome="Ana", email="ana@example.com", senha="segredo123")

    with pytest.raises(EmailJaCadastradoError):
        service.cadastrar(nome="Outra Ana", email="ana@example.com", senha="outrasenha")


def test_autenticar_com_credenciais_corretas_retorna_usuario():
    service = _service()
    service.cadastrar(nome="Ana", email="ana@example.com", senha="segredo123")

    usuario = service.autenticar(email="ana@example.com", senha="segredo123")

    assert usuario.email == "ana@example.com"


def test_autenticar_com_senha_incorreta_lanca_erro():
    service = _service()
    service.cadastrar(nome="Ana", email="ana@example.com", senha="segredo123")

    with pytest.raises(CredenciaisInvalidasError):
        service.autenticar(email="ana@example.com", senha="senhaerrada")


def test_autenticar_com_email_inexistente_lanca_erro():
    service = _service()

    with pytest.raises(CredenciaisInvalidasError):
        service.autenticar(email="naoexiste@example.com", senha="qualquer")


def test_buscar_por_id_retorna_usuario_cadastrado():
    service = _service()
    usuario = service.cadastrar(nome="Ana", email="ana@example.com", senha="segredo123")

    encontrado = service.buscar_por_id(usuario.id)

    assert encontrado is not None
    assert encontrado.email == "ana@example.com"


def test_buscar_por_id_inexistente_retorna_none():
    service = _service()

    assert service.buscar_por_id(uuid4()) is None
