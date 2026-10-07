import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from app.integrations.web_push.base64url import codificar, decodificar
from app.integrations.web_push.cifragem import TAMANHO_MAXIMO_PAYLOAD, cifrar
from tests.fixtures.navegador_falso import NavegadorFalso

_AS_PRIVADA = "yfWPiYE-n46HLnH0KqZOF1fJJU3MYrct3AELtAQ-oRw"
_UA_PUBLICA = (
    "BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-JvLexhqUzORcxaOzi6-AYWXvTBHm4bjyPjs7Vd8pZGH6SRpkNtoIAiw4"
)
_AUTH = "BTBZMqHH6r4Tts7J_aSIgg"
_SALT = "DGv6ra1nlYgDCS1FRnbzlw"
_CABECALHO = (
    "DGv6ra1nlYgDCS1FRnbzlwAAEABBBP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27ml"
    "mlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A8"
)
_CIFRADO = "8pfeW0KbunFT06SuDKoJH9Ql87S1QUrdirN6GcG7sFz1y1sqLgVi1VhjVkHsUoEsbI_0LpXMuGvnzQ"


def test_vetor_do_apendice_a_da_rfc_8291():
    chave_efemera = ec.derive_private_key(
        int.from_bytes(decodificar(_AS_PRIVADA), "big"), ec.SECP256R1()
    )

    corpo = cifrar(
        b"When I grow up, I want to be a watermelon",
        _UA_PUBLICA,
        _AUTH,
        chave_efemera=chave_efemera,
        salt=decodificar(_SALT),
    )

    assert corpo == decodificar(_CABECALHO) + decodificar(_CIFRADO)


def test_ida_e_volta_com_chaves_geradas_e_acentos():
    navegador = NavegadorFalso()
    texto = '{"title": "Alerta de preço"}'.encode()

    corpo = cifrar(texto, navegador.p256dh, navegador.auth)

    assert navegador.decifrar(corpo) == texto


def test_cada_cifragem_usa_salt_e_chave_novos():
    navegador = NavegadorFalso()

    primeiro = cifrar(b"x", navegador.p256dh, navegador.auth)
    segundo = cifrar(b"x", navegador.p256dh, navegador.auth)

    assert primeiro[:16] != segundo[:16]
    assert primeiro[21:86] != segundo[21:86]


def test_cabecalho_tem_registro_4096_e_chave_de_65_bytes():
    navegador = NavegadorFalso()

    corpo = cifrar(b"x", navegador.p256dh, navegador.auth)

    assert corpo[16:21] == b"\x00\x00\x10\x00\x41"
    assert corpo[21] == 0x04


def test_payload_no_limite_e_aceito_e_acima_e_recusado():
    navegador = NavegadorFalso()

    corpo = cifrar(b"a" * TAMANHO_MAXIMO_PAYLOAD, navegador.p256dh, navegador.auth)
    assert len(corpo) == 4096

    with pytest.raises(ValueError):
        cifrar(b"a" * (TAMANHO_MAXIMO_PAYLOAD + 1), navegador.p256dh, navegador.auth)


@pytest.mark.parametrize("texto", ["abc$", "a b", "é"])
def test_decodificar_recusa_caracteres_invalidos(texto):
    with pytest.raises(ValueError):
        decodificar(texto)


def test_codificar_e_decodificar_sem_padding():
    assert codificar(b"\xfb\xff") == "-_8"
    assert decodificar("-_8") == b"\xfb\xff"
