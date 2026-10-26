from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.domain.entities.refresh_token import RefreshToken
from app.domain.entities.usuario import Usuario
from app.services.exceptions import CredenciaisInvalidasError, TokenRedefinicaoInvalidoError
from app.services.senha_service import SenhaService
from tests.fixtures.fake_refresh_token_repository import FakeRefreshTokenRepository
from tests.fixtures.fake_usuario_repository import FakeUsuarioRepository

_AGORA = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
_URL = "https://app.test/redefinir?token="


def _cenario():
    usuarios = FakeUsuarioRepository()
    tokens = FakeRefreshTokenRepository()
    usuario = Usuario.criar(uuid4(), "Ana", "ana@example.com", "segredo123", _AGORA)
    usuarios.salvar(usuario)
    tokens.salvar(
        RefreshToken(uuid4(), usuario.id, "h" * 64, uuid4(), _AGORA, _AGORA + timedelta(days=30))
    )
    service = SenhaService(usuarios, tokens, "segredo-jwt", 30, _URL, agora=lambda: _AGORA)
    return service, usuarios, tokens, usuario


def _token_do_email(corpo: str) -> str:
    return corpo.split(_URL, 1)[1].split()[0]


def test_alterar_troca_a_senha_e_revoga_as_sessoes():
    service, _, tokens, usuario = _cenario()

    service.alterar(usuario, "segredo123", "novasenha456")

    assert usuario.autenticar("novasenha456")
    assert all(t.esta_revogado() for t in tokens.listar_todos())


def test_alterar_com_senha_atual_errada_nao_troca():
    service, _, tokens, usuario = _cenario()

    with pytest.raises(CredenciaisInvalidasError):
        service.alterar(usuario, "errada", "novasenha456")

    assert usuario.autenticar("segredo123")
    assert not any(t.esta_revogado() for t in tokens.listar_todos())


def test_recuperacao_de_email_desconhecido_nao_gera_email():
    service, *_ = _cenario()

    assert service.preparar_recuperacao("ninguem@example.com") is None


def test_recuperacao_de_usuario_inativo_nao_gera_email():
    service, _, _, usuario = _cenario()
    usuario.ativo = False

    assert service.preparar_recuperacao("ana@example.com") is None


def test_fluxo_completo_de_redefinicao():
    service, usuarios, tokens, usuario = _cenario()

    email = service.preparar_recuperacao("ana@example.com")
    service.redefinir(_token_do_email(email.corpo), "novasenha456")

    assert email.destinatario == "ana@example.com"
    assert usuarios.buscar_por_id(usuario.id).autenticar("novasenha456")
    assert all(t.esta_revogado() for t in tokens.listar_todos())


def test_token_de_redefinicao_so_vale_uma_vez():
    service, *_ = _cenario()
    token = _token_do_email(service.preparar_recuperacao("ana@example.com").corpo)
    service.redefinir(token, "novasenha456")

    with pytest.raises(TokenRedefinicaoInvalidoError):
        service.redefinir(token, "outrasenha789")


def test_token_invalido_e_recusado():
    service, *_ = _cenario()

    with pytest.raises(TokenRedefinicaoInvalidoError):
        service.redefinir("nao-e-um-jwt", "novasenha456")
