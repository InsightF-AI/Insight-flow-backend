import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.services.dispositivo_push_service import DispositivoPushService
from app.services.exceptions import TokenPushInvalidoError
from tests.fixtures.fake_dispositivo_push_repository import FakeDispositivoPushRepository

_INICIO = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
_TOKEN = "ExponentPushToken[abc123]"


class _Relogio:
    def __init__(self) -> None:
        self.agora = _INICIO

    def __call__(self) -> datetime:
        return self.agora


def _cenario():
    repositorio = FakeDispositivoPushRepository()
    relogio = _Relogio()
    return DispositivoPushService(repositorio, agora=relogio), repositorio, relogio


def test_registrar_token_novo_cria_dispositivo_ativo():
    service, repositorio, _ = _cenario()
    usuario_id = uuid4()

    criado = service.registrar(usuario_id, _TOKEN)

    assert criado is True
    (dispositivo,) = repositorio.listar_todos()
    assert dispositivo.usuario_id == usuario_id
    assert dispositivo.token == _TOKEN
    assert dispositivo.ativo is True
    assert dispositivo.criado_em == _INICIO


def test_registrar_aceita_o_prefixo_expo_push_token():
    service, repositorio, _ = _cenario()

    service.registrar(uuid4(), "ExpoPushToken[xyz]")

    assert repositorio.listar_todos()[0].token == "ExpoPushToken[xyz]"


def test_registrar_remove_espacos_nas_pontas():
    service, repositorio, _ = _cenario()

    service.registrar(uuid4(), f"  {_TOKEN}\n")

    assert repositorio.listar_todos()[0].token == _TOKEN


def test_registrar_token_existente_do_mesmo_usuario_reativa_sem_duplicar():
    service, repositorio, relogio = _cenario()
    usuario_id = uuid4()
    service.registrar(usuario_id, _TOKEN)
    repositorio.desativar_por_token(_TOKEN, _INICIO)
    relogio.agora = _INICIO + timedelta(hours=1)

    criado = service.registrar(usuario_id, _TOKEN)

    assert criado is False
    (dispositivo,) = repositorio.listar_todos()
    assert dispositivo.ativo is True
    assert dispositivo.atualizado_em == _INICIO + timedelta(hours=1)


def test_registrar_token_de_outra_conta_transfere_para_o_usuario_atual():
    service, repositorio, _ = _cenario()
    anterior = uuid4()
    atual = uuid4()
    service.registrar(anterior, _TOKEN)

    service.registrar(atual, _TOKEN)

    (dispositivo,) = repositorio.listar_todos()
    assert dispositivo.usuario_id == atual
    assert repositorio.listar_ativos_por_usuario(anterior) == []


@pytest.mark.parametrize(
    "token",
    [
        "",
        "abc",
        "ExponentPushToken[]",
        "exponentpushtoken[abc]",
        "ExponentPushToken[abc",
        "ExponentPushToken[" + "a" * 250 + "]",
    ],
)
def test_registrar_formato_invalido_lanca_erro_e_nao_salva(token):
    service, repositorio, _ = _cenario()

    with pytest.raises(TokenPushInvalidoError):
        service.registrar(uuid4(), token)

    assert repositorio.listar_todos() == []


def test_remover_desativa_token_do_proprio_usuario():
    service, repositorio, _ = _cenario()
    usuario_id = uuid4()
    service.registrar(usuario_id, _TOKEN)

    service.remover(usuario_id, _TOKEN)

    assert repositorio.listar_ativos_por_usuario(usuario_id) == []


def test_remover_ignora_token_de_outro_usuario():
    service, repositorio, _ = _cenario()
    dono = uuid4()
    service.registrar(dono, _TOKEN)

    service.remover(uuid4(), _TOKEN)

    assert len(repositorio.listar_ativos_por_usuario(dono)) == 1


def test_remover_token_desconhecido_nao_lanca_erro():
    service, _, _ = _cenario()

    service.remover(uuid4(), _TOKEN)


def test_registrar_loga_sem_expor_o_token(caplog):
    service, _, _ = _cenario()
    caplog.set_level(logging.INFO)

    service.registrar(uuid4(), _TOKEN)

    registro = next(
        r for r in caplog.records if getattr(r, "evento", None) == "dispositivo_registrado"
    )
    assert registro.transferido is False
    assert _TOKEN not in str(vars(registro))
