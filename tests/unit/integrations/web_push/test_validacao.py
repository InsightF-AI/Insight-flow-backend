import pytest

from app.integrations.web_push.base64url import codificar
from app.integrations.web_push.validacao import (
    HOSTS_PERMITIDOS_PADRAO,
    InscricaoWebPushInvalidaError,
    validar_inscricao,
)
from tests.fixtures.navegador_falso import NavegadorFalso

_NAVEGADOR = NavegadorFalso()


def _validar(endpoint: str, p256dh: str | None = None, auth: str | None = None) -> None:
    validar_inscricao(
        endpoint,
        p256dh if p256dh is not None else _NAVEGADOR.p256dh,
        auth if auth is not None else _NAVEGADOR.auth,
        HOSTS_PERMITIDOS_PADRAO,
    )


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://fcm.googleapis.com/fcm/send/abc",
        "https://FCM.googleapis.com:443/fcm/send/abc",
        "https://updates.push.services.mozilla.com/wpush/v2/abc",
        "https://web.push.apple.com/QGw",
        "https://wns2-par02p.notify.windows.com/w/?token=abc",
    ],
)
def test_endpoints_de_servicos_conhecidos_sao_aceitos(endpoint):
    _validar(endpoint)


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://fcm.googleapis.com/fcm/send/abc",
        "https://fcm.googleapis.com.evil.com/x",
        "https://evil.com/fcm.googleapis.com",
        "https://usuario:senha@fcm.googleapis.com/x",
        "https://push.apple.com/x",
        "https://xpush.apple.com/x",
        "https://localhost/x",
        "https://169.254.169.254/latest",
        "fcm.googleapis.com/fcm/send/abc",
        "https://fcm.googleapis.com/" + "a" * 1024,
        "https://fcm.googleapis.com:abc/x",
        "https://fcm.googleapis.com:99999/x",
        "https://fcm.googleapis.com:8443/x",
    ],
)
def test_endpoints_fora_da_lista_ou_malformados_sao_recusados(endpoint):
    with pytest.raises(InscricaoWebPushInvalidaError):
        _validar(endpoint)


@pytest.mark.parametrize(
    "p256dh",
    [
        "abc$",
        codificar(b"\x04" + b"\x00" * 64),
        codificar(b"\x05" + b"\x01" * 64),
        codificar(b"\x04" + b"\x01" * 10),
    ],
)
def test_p256dh_invalido_e_recusado(p256dh):
    with pytest.raises(InscricaoWebPushInvalidaError):
        _validar("https://fcm.googleapis.com/fcm/send/abc", p256dh=p256dh)


@pytest.mark.parametrize("auth", ["abc$", codificar(b"\x01" * 15), codificar(b"\x01" * 17)])
def test_auth_invalido_e_recusado(auth):
    with pytest.raises(InscricaoWebPushInvalidaError):
        _validar("https://fcm.googleapis.com/fcm/send/abc", auth=auth)


def test_lista_customizada_substitui_a_padrao():
    validar_inscricao(
        "https://push.exemplo.net/x", _NAVEGADOR.p256dh, _NAVEGADOR.auth, ["push.exemplo.net"]
    )
    with pytest.raises(InscricaoWebPushInvalidaError):
        validar_inscricao(
            "https://fcm.googleapis.com/x", _NAVEGADOR.p256dh, _NAVEGADOR.auth, ["push.exemplo.net"]
        )
