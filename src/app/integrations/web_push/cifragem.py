from __future__ import annotations

import os
import struct

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from app.integrations.web_push.base64url import decodificar

TAMANHO_REGISTRO = 4096
TAMANHO_MAXIMO_PAYLOAD = 3993

_DELIMITADOR = b"\x02"


def _hkdf(salt: bytes, ikm: bytes, info: bytes, tamanho: int) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=tamanho, salt=salt, info=info).derive(ikm)


def cifrar(
    texto: bytes,
    p256dh: str,
    auth: str,
    chave_efemera: ec.EllipticCurvePrivateKey | None = None,
    salt: bytes | None = None,
) -> bytes:
    if len(texto) > TAMANHO_MAXIMO_PAYLOAD:
        raise ValueError("Payload de web push grande demais")

    ua_publica = decodificar(p256dh)
    chave_navegador = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_publica)
    chave_efemera = chave_efemera or ec.generate_private_key(ec.SECP256R1())
    salt = salt or os.urandom(16)
    as_publica = chave_efemera.public_key().public_bytes(
        Encoding.X962, PublicFormat.UncompressedPoint
    )

    segredo_ecdh = chave_efemera.exchange(ec.ECDH(), chave_navegador)
    ikm = _hkdf(decodificar(auth), segredo_ecdh, b"WebPush: info\x00" + ua_publica + as_publica, 32)
    cek = _hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = _hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)
    cifrado = AESGCM(cek).encrypt(nonce, texto + _DELIMITADOR, None)

    return salt + struct.pack("!IB", TAMANHO_REGISTRO, len(as_publica)) + as_publica + cifrado
