import hashlib
import logging
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.core.security import decodificar_token
from app.domain.entities.usuario import Usuario
from app.services.exceptions import RefreshTokenInvalidoError
from app.services.refresh_token_service import RefreshTokenService
from tests.fixtures.fake_refresh_token_repository import FakeRefreshTokenRepository
from tests.fixtures.fake_usuario_repository import FakeUsuarioRepository

_SEGREDO = "segredo-de-teste"
_INICIO = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)


class _Relogio:
    def __init__(self) -> None:
        self.agora = _INICIO

    def __call__(self) -> datetime:
        return self.agora


def _cenario(ativo: bool = True):
    usuarios = FakeUsuarioRepository()
    usuario = Usuario.criar(
        id=uuid4(), nome="Ana", email="ana@example.com", senha="segredo123", criado_em=_INICIO
    )
    usuario.ativo = ativo
    usuarios.salvar(usuario)
    tokens = FakeRefreshTokenRepository()
    relogio = _Relogio()
    service = RefreshTokenService(
        tokens,
        usuarios,
        jwt_secret_key=_SEGREDO,
        access_expiracao_minutos=30,
        refresh_expiracao_dias=30,
        agora=relogio,
    )
    return service, tokens, usuario, relogio


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def test_emitir_grava_so_o_hash_e_o_access_decodifica_para_o_usuario():
    service, tokens, usuario, _ = _cenario()

    par = service.emitir(usuario.id)

    salvos = tokens.listar_todos()
    assert len(salvos) == 1
    assert salvos[0].token_hash == _hash(par.refresh_token)
    assert par.refresh_token not in {t.token_hash for t in salvos}
    assert salvos[0].expira_em == _INICIO + timedelta(days=30)
    assert decodificar_token(par.access_token, _SEGREDO) == usuario.id
    assert par.expires_in == 1800


def test_renovar_rotaciona_na_mesma_familia():
    service, tokens, usuario, _ = _cenario()
    primeiro = service.emitir(usuario.id)

    segundo = service.renovar(primeiro.refresh_token)

    assert segundo.refresh_token != primeiro.refresh_token
    assert decodificar_token(segundo.access_token, _SEGREDO) == usuario.id
    antigo = tokens.buscar_por_hash(_hash(primeiro.refresh_token))
    novo = tokens.buscar_por_hash(_hash(segundo.refresh_token))
    assert antigo.esta_revogado() is True
    assert novo.esta_revogado() is False
    assert novo.familia_id == antigo.familia_id


def test_reuso_de_token_revogado_derruba_a_familia_inclusive_o_token_rotacionado():
    service, _, usuario, _ = _cenario()
    primeiro = service.emitir(usuario.id)
    segundo = service.renovar(primeiro.refresh_token)

    with pytest.raises(RefreshTokenInvalidoError):
        service.renovar(primeiro.refresh_token)
    with pytest.raises(RefreshTokenInvalidoError):
        service.renovar(segundo.refresh_token)


def test_token_expirado_e_invalido():
    service, _, usuario, relogio = _cenario()
    par = service.emitir(usuario.id)
    relogio.agora = _INICIO + timedelta(days=30)

    with pytest.raises(RefreshTokenInvalidoError):
        service.renovar(par.refresh_token)


def test_token_inexistente_e_invalido():
    service, _, _, _ = _cenario()

    with pytest.raises(RefreshTokenInvalidoError):
        service.renovar("token-que-nunca-existiu")


def test_usuario_inativo_nao_renova():
    service, _, usuario, _ = _cenario(ativo=False)
    par = service.emitir(usuario.id)

    with pytest.raises(RefreshTokenInvalidoError):
        service.renovar(par.refresh_token)


def test_revogar_derruba_a_familia():
    service, _, usuario, _ = _cenario()
    primeiro = service.emitir(usuario.id)
    segundo = service.renovar(primeiro.refresh_token)

    service.revogar(segundo.refresh_token)

    with pytest.raises(RefreshTokenInvalidoError):
        service.renovar(segundo.refresh_token)


def test_revogar_token_desconhecido_nao_lanca_erro():
    service, _, _, _ = _cenario()

    service.revogar("token-que-nunca-existiu")


class _RepositorioComLeituraAtrasada(FakeRefreshTokenRepository):
    def buscar_por_hash(self, token_hash: str):
        token = super().buscar_por_hash(token_hash)
        return replace(token, revogado_em=None) if token is not None else None


def test_renovacao_concorrente_que_perde_a_corrida_e_tratada_como_reuso():
    usuarios = FakeUsuarioRepository()
    usuario = Usuario.criar(
        id=uuid4(), nome="Ana", email="ana@example.com", senha="segredo123", criado_em=_INICIO
    )
    usuarios.salvar(usuario)
    tokens = _RepositorioComLeituraAtrasada()
    service = RefreshTokenService(
        tokens,
        usuarios,
        jwt_secret_key=_SEGREDO,
        access_expiracao_minutos=30,
        refresh_expiracao_dias=30,
        agora=_Relogio(),
    )
    primeiro = service.emitir(usuario.id)
    service.renovar(primeiro.refresh_token)

    with pytest.raises(RefreshTokenInvalidoError):
        service.renovar(primeiro.refresh_token)

    assert all(token.esta_revogado() for token in tokens.listar_todos())


def _registros(caplog, nome: str = "app.services.refresh_token_service"):
    return [r for r in caplog.records if r.name == nome]


def test_reuso_de_token_e_logado_como_aviso_com_o_usuario(caplog):
    service, _, usuario, _ = _cenario()
    primeiro = service.emitir(usuario.id)
    service.renovar(primeiro.refresh_token)
    caplog.set_level(logging.INFO)

    with pytest.raises(RefreshTokenInvalidoError):
        service.renovar(primeiro.refresh_token)

    registro = _registros(caplog)[-1]
    assert registro.levelno == logging.WARNING
    assert registro.usuario_id == str(usuario.id)
    assert registro.evento == "refresh_reutilizado"


def test_refresh_invalido_e_logado_sem_dados_do_token(caplog):
    service, _, _, _ = _cenario()
    caplog.set_level(logging.INFO)

    with pytest.raises(RefreshTokenInvalidoError):
        service.renovar("token-que-nunca-existiu")

    registro = _registros(caplog)[-1]
    assert registro.evento == "refresh_invalido"
    assert "token-que-nunca-existiu" not in registro.getMessage()


def test_logout_e_logado_com_o_usuario(caplog):
    service, _, usuario, _ = _cenario()
    par = service.emitir(usuario.id)
    caplog.set_level(logging.INFO)

    service.revogar(par.refresh_token)

    registro = _registros(caplog)[-1]
    assert registro.evento == "logout"
    assert registro.usuario_id == str(usuario.id)
