import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.integrations.web_push.validacao import (
    HOSTS_PERMITIDOS_PADRAO,
    InscricaoWebPushInvalidaError,
)
from app.services.inscricao_web_push_service import InscricaoWebPushService
from tests.fixtures.fake_inscricao_web_push_repository import FakeInscricaoWebPushRepository
from tests.fixtures.navegador_falso import NavegadorFalso

_INICIO = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
_ENDPOINT = "https://fcm.googleapis.com/fcm/send/abc"


class _Relogio:
    def __init__(self) -> None:
        self.agora = _INICIO

    def __call__(self) -> datetime:
        return self.agora


def _cenario():
    repositorio = FakeInscricaoWebPushRepository()
    relogio = _Relogio()
    service = InscricaoWebPushService(repositorio, HOSTS_PERMITIDOS_PADRAO, agora=relogio)
    return service, repositorio, relogio


def test_registrar_nova_inscricao_cria():
    service, repositorio, _ = _cenario()
    navegador = NavegadorFalso()
    usuario_id = uuid4()

    criada = service.registrar(usuario_id, _ENDPOINT, navegador.p256dh, navegador.auth)

    assert criada is True
    (inscricao,) = repositorio.listar_todos()
    assert inscricao.usuario_id == usuario_id
    assert inscricao.p256dh == navegador.p256dh
    assert inscricao.criado_em == _INICIO


def test_registrar_de_novo_com_chaves_novas_atualiza_sem_duplicar():
    service, repositorio, relogio = _cenario()
    usuario_id = uuid4()
    primeiro = NavegadorFalso()
    service.registrar(usuario_id, _ENDPOINT, primeiro.p256dh, primeiro.auth)
    segundo = NavegadorFalso()
    relogio.agora = _INICIO + timedelta(days=1)

    criada = service.registrar(usuario_id, _ENDPOINT, segundo.p256dh, segundo.auth)

    assert criada is False
    (inscricao,) = repositorio.listar_todos()
    assert inscricao.p256dh == segundo.p256dh
    assert inscricao.auth == segundo.auth
    assert inscricao.atualizado_em == _INICIO + timedelta(days=1)


def test_registrar_inscricao_de_outra_conta_transfere():
    service, repositorio, _ = _cenario()
    navegador = NavegadorFalso()
    anterior, atual = uuid4(), uuid4()
    service.registrar(anterior, _ENDPOINT, navegador.p256dh, navegador.auth)

    service.registrar(atual, _ENDPOINT, navegador.p256dh, navegador.auth)

    (inscricao,) = repositorio.listar_todos()
    assert inscricao.usuario_id == atual


def test_registrar_invalida_lanca_erro_e_nao_salva():
    service, repositorio, _ = _cenario()
    navegador = NavegadorFalso()

    with pytest.raises(InscricaoWebPushInvalidaError):
        service.registrar(uuid4(), "https://evil.com/x", navegador.p256dh, navegador.auth)

    assert repositorio.listar_todos() == []


def test_remover_apaga_so_do_dono():
    service, repositorio, _ = _cenario()
    navegador = NavegadorFalso()
    dono = uuid4()
    service.registrar(dono, _ENDPOINT, navegador.p256dh, navegador.auth)

    service.remover(uuid4(), _ENDPOINT)
    assert len(repositorio.listar_todos()) == 1

    service.remover(dono, _ENDPOINT)
    assert repositorio.listar_todos() == []


def test_remover_desconhecida_nao_lanca_erro():
    service, _, _ = _cenario()

    service.remover(uuid4(), _ENDPOINT)


def test_registrar_loga_sem_o_endpoint(caplog):
    service, _, _ = _cenario()
    navegador = NavegadorFalso()
    caplog.set_level(logging.INFO)

    service.registrar(uuid4(), _ENDPOINT, navegador.p256dh, navegador.auth)

    registro = next(
        r for r in caplog.records if getattr(r, "evento", None) == "inscricao_web_push_registrada"
    )
    assert registro.transferida is False
    assert _ENDPOINT not in str(vars(registro))
