import pytest

from app.api.deps import get_settings
from app.core.config import Settings
from app.integrations.web_push.vapid import ChaveVapid
from app.main import app
from tests.fixtures.navegador_falso import NavegadorFalso

_ENDPOINT = "https://fcm.googleapis.com/fcm/send/abc"


def _corpo(navegador: NavegadorFalso, endpoint: str = _ENDPOINT) -> dict:
    return {
        "endpoint": endpoint,
        "expirationTime": None,
        "keys": {"p256dh": navegador.p256dh, "auth": navegador.auth},
    }


@pytest.fixture
def chave_vapid() -> ChaveVapid:
    return ChaveVapid.gerar()


@pytest.fixture
def com_web_push_configurado(chave_vapid):
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,
        web_push_vapid_chave_privada=chave_vapid.privada_base64url(),
        web_push_vapid_contato="mailto:a@b.c",
    )
    yield
    app.dependency_overrides.pop(get_settings, None)


def test_chave_publica_sem_configuracao_retorna_503(client):
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)

    resposta = client.get("/api/v1/web-push/chave-publica")

    app.dependency_overrides.pop(get_settings, None)
    assert resposta.status_code == 503
    assert resposta.json() == {"detail": "Web push nao configurado"}


def test_chave_publica_configurada_e_publica(client, chave_vapid, com_web_push_configurado):
    resposta = client.get("/api/v1/web-push/chave-publica")

    assert resposta.status_code == 200
    assert resposta.json() == {"chave_publica": chave_vapid.publica_base64url()}


def test_registrar_sem_autenticacao_retorna_401(client):
    resposta = client.post("/api/v1/web-push/inscricoes", json=_corpo(NavegadorFalso()))

    assert resposta.status_code == 401


def test_registrar_nova_retorna_201(client, auth_headers, inscricao_web_push_repository):
    resposta = client.post(
        "/api/v1/web-push/inscricoes", json=_corpo(NavegadorFalso()), headers=auth_headers
    )

    assert resposta.status_code == 201
    assert resposta.json() == {"endpoint": _ENDPOINT}
    assert len(inscricao_web_push_repository.listar_todos()) == 1


def test_registrar_repetida_retorna_200(client, auth_headers):
    navegador = NavegadorFalso()
    client.post("/api/v1/web-push/inscricoes", json=_corpo(navegador), headers=auth_headers)

    resposta = client.post(
        "/api/v1/web-push/inscricoes", json=_corpo(navegador), headers=auth_headers
    )

    assert resposta.status_code == 200


def test_registrar_host_nao_permitido_retorna_422(client, auth_headers):
    resposta = client.post(
        "/api/v1/web-push/inscricoes",
        json=_corpo(NavegadorFalso(), "https://evil.com/x"),
        headers=auth_headers,
    )

    assert resposta.status_code == 422
    assert resposta.json() == {"detail": "Inscricao de web push invalida"}


def test_registrar_sem_keys_retorna_422(client, auth_headers):
    resposta = client.post(
        "/api/v1/web-push/inscricoes", json={"endpoint": _ENDPOINT}, headers=auth_headers
    )

    assert resposta.status_code == 422


def test_remover_retorna_204(client, auth_headers, inscricao_web_push_repository):
    client.post("/api/v1/web-push/inscricoes", json=_corpo(NavegadorFalso()), headers=auth_headers)

    resposta = client.delete(
        "/api/v1/web-push/inscricoes", params={"endpoint": _ENDPOINT}, headers=auth_headers
    )

    assert resposta.status_code == 204
    assert inscricao_web_push_repository.listar_todos() == []


def test_remover_desconhecida_retorna_204(client, auth_headers):
    resposta = client.delete(
        "/api/v1/web-push/inscricoes", params={"endpoint": _ENDPOINT}, headers=auth_headers
    )

    assert resposta.status_code == 204


def test_remover_sem_autenticacao_retorna_401(client):
    resposta = client.delete("/api/v1/web-push/inscricoes", params={"endpoint": _ENDPOINT})

    assert resposta.status_code == 401
