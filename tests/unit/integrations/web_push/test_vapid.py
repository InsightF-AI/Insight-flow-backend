import json
from datetime import UTC, datetime

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

from app.integrations.web_push.base64url import decodificar
from app.integrations.web_push.vapid import ChaveVapid
from app.scripts import gerar_chaves_vapid

_AGORA = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
_PRIVADA_RFC = "yfWPiYE-n46HLnH0KqZOF1fJJU3MYrct3AELtAQ-oRw"
_PUBLICA_RFC = (
    "BP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27mlmlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A8"
)


def _ler(cabecalho: str, chave_publica: str) -> tuple[dict, dict]:
    assert cabecalho.startswith("vapid t=")
    token, k = cabecalho[len("vapid t=") :].split(", k=")
    assert k == chave_publica
    parte_cabecalho, parte_corpo, assinatura = token.split(".")
    bruto = decodificar(assinatura)
    assert len(bruto) == 64
    publica = ec.EllipticCurvePublicKey.from_encoded_point(
        ec.SECP256R1(), decodificar(chave_publica)
    )
    publica.verify(
        encode_dss_signature(int.from_bytes(bruto[:32], "big"), int.from_bytes(bruto[32:], "big")),
        f"{parte_cabecalho}.{parte_corpo}".encode(),
        ec.ECDSA(hashes.SHA256()),
    )
    return json.loads(decodificar(parte_cabecalho)), json.loads(decodificar(parte_corpo))


def test_chave_publica_e_derivada_da_privada():
    assert ChaveVapid.de_base64url(_PRIVADA_RFC).publica_base64url() == _PUBLICA_RFC


def test_cabecalho_authorization_com_jwt_es256_valido():
    chave = ChaveVapid.de_base64url(_PRIVADA_RFC)

    cabecalho = chave.cabecalho_authorization(
        "https://fcm.googleapis.com/fcm/send/abc", "mailto:equipe@exemplo.com", _AGORA
    )

    cab, corpo = _ler(cabecalho, _PUBLICA_RFC)
    assert cab == {"typ": "JWT", "alg": "ES256"}
    assert corpo == {
        "aud": "https://fcm.googleapis.com",
        "exp": int(_AGORA.timestamp()) + 12 * 3600,
        "sub": "mailto:equipe@exemplo.com",
    }


def test_aud_mantem_porta_explicita_e_normaliza_host():
    chave = ChaveVapid.gerar()

    cabecalho = chave.cabecalho_authorization(
        "https://FCM.googleapis.com:8443/fcm/send/abc", "mailto:a@b.c", _AGORA
    )

    _, corpo = _ler(cabecalho, chave.publica_base64url())
    assert corpo["aud"] == "https://fcm.googleapis.com:8443"


def test_aud_omite_a_porta_padrao_443():
    chave = ChaveVapid.gerar()

    cabecalho = chave.cabecalho_authorization(
        "https://fcm.googleapis.com:443/fcm/send/abc", "mailto:a@b.c", _AGORA
    )

    _, corpo = _ler(cabecalho, chave.publica_base64url())
    assert corpo["aud"] == "https://fcm.googleapis.com"


def test_gerar_e_reler_a_chave():
    chave = ChaveVapid.gerar()

    relida = ChaveVapid.de_base64url(chave.privada_base64url())

    assert relida.publica_base64url() == chave.publica_base64url()
    assert len(decodificar(chave.privada_base64url())) == 32


@pytest.mark.parametrize("valor", ["", "abc$", "AAAA", "A" * 43])
def test_chave_privada_invalida_lanca_value_error(valor):
    with pytest.raises(ValueError):
        ChaveVapid.de_base64url(valor)


def test_script_imprime_par_de_chaves(capsys):
    gerar_chaves_vapid.main()

    saida = capsys.readouterr().out.splitlines()
    privada = saida[0].removeprefix("WEB_PUSH_VAPID_CHAVE_PRIVADA=")
    assert ChaveVapid.de_base64url(privada).publica_base64url() == saida[1].removeprefix(
        "Chave publica: "
    )
