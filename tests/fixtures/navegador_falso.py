from __future__ import annotations

import os
import struct

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from app.integrations.web_push.base64url import codificar


def _hkdf(salt: bytes, ikm: bytes, info: bytes, tamanho: int) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=tamanho, salt=salt, info=info).derive(ikm)


class NavegadorFalso:
    def __init__(self) -> None:
        self._privada = ec.generate_private_key(ec.SECP256R1())
        self._segredo = os.urandom(16)

    @property
    def publica(self) -> bytes:
        return self._privada.public_key().public_bytes(
            Encoding.X962, PublicFormat.UncompressedPoint
        )

    @property
    def p256dh(self) -> str:
        return codificar(self.publica)

    @property
    def auth(self) -> str:
        return codificar(self._segredo)

    def decifrar(self, corpo: bytes) -> bytes:
        salt = corpo[:16]
        _, tamanho_id = struct.unpack("!IB", corpo[16:21])
        as_publica = corpo[21 : 21 + tamanho_id]
        cifrado = corpo[21 + tamanho_id :]
        segredo_ecdh = self._privada.exchange(
            ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), as_publica)
        )
        ikm = _hkdf(
            self._segredo, segredo_ecdh, b"WebPush: info\x00" + self.publica + as_publica, 32
        )
        cek = _hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
        nonce = _hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)
        texto = AESGCM(cek).decrypt(nonce, cifrado, None)
        assert texto.endswith(b"\x02")
        return texto[:-1]
