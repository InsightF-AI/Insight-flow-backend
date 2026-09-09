from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.api.deps import get_usuario_atual
from app.core.config import Settings
from app.core.security import criar_token
from app.domain.entities.usuario import Usuario
from app.services.usuario_service import UsuarioService
from tests.fixtures.fake_usuario_repository import FakeUsuarioRepository

SETTINGS = Settings(jwt_secret_key="segredo-de-teste", jwt_expiration_minutes=60)


def _service_com_usuario() -> tuple[UsuarioService, Usuario]:
    service = UsuarioService(FakeUsuarioRepository())
    usuario = service.cadastrar(nome="Ana", email="ana@example.com", senha="segredo123")
    return service, usuario


def _credenciais(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_token_valido_retorna_o_usuario_correspondente():
    service, usuario = _service_com_usuario()
    token = criar_token(usuario.id, SETTINGS.jwt_secret_key, SETTINGS.jwt_expiration_minutes)

    encontrado = get_usuario_atual(_credenciais(token), service, SETTINGS)

    assert encontrado.id == usuario.id


def test_token_com_assinatura_invalida_lanca_401():
    service, usuario = _service_com_usuario()
    token = criar_token(usuario.id, "outro-segredo", SETTINGS.jwt_expiration_minutes)

    with pytest.raises(HTTPException) as exc_info:
        get_usuario_atual(_credenciais(token), service, SETTINGS)

    assert exc_info.value.status_code == 401


def test_token_de_usuario_inexistente_lanca_401():
    service, _ = _service_com_usuario()
    token = criar_token(uuid4(), SETTINGS.jwt_secret_key, SETTINGS.jwt_expiration_minutes)

    with pytest.raises(HTTPException) as exc_info:
        get_usuario_atual(_credenciais(token), service, SETTINGS)

    assert exc_info.value.status_code == 401
