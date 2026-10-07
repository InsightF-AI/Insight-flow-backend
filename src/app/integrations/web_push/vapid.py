from __future__ import annotations

import json
from datetime import datetime, timedelta
from urllib.parse import urlsplit

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from app.integrations.web_push.base64url import codificar, decodificar

_VALIDADE_TOKEN = timedelta(hours=12)
_CABECALHO_JWT = {"typ": "JWT", "alg": "ES256"}


def _json_base64url(dados: dict) -> str:
    return codificar(json.dumps(dados, separators=(",", ":")).encode())


def _origem(endpoint: str) -> str:
    url = urlsplit(endpoint)
    porta = f":{url.port}" if url.port and url.port != 443 else ""
    return f"{url.scheme}://{url.hostname}{porta}"


class ChaveVapid:
    def __init__(self, privada: ec.EllipticCurvePrivateKey):
        self._privada = privada

    @classmethod
    def de_base64url(cls, chave_privada: str) -> ChaveVapid:
        bruto = decodificar(chave_privada)
        if len(bruto) != 32:
            raise ValueError("Chave VAPID privada deve ter 32 bytes")
        return cls(ec.derive_private_key(int.from_bytes(bruto, "big"), ec.SECP256R1()))

    @classmethod
    def gerar(cls) -> ChaveVapid:
        return cls(ec.generate_private_key(ec.SECP256R1()))

    def privada_base64url(self) -> str:
        return codificar(self._privada.private_numbers().private_value.to_bytes(32, "big"))

    def publica_base64url(self) -> str:
        return codificar(
            self._privada.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
        )

    def cabecalho_authorization(self, endpoint: str, contato: str, agora: datetime) -> str:
        claims = {
            "aud": _origem(endpoint),
            "exp": int((agora + _VALIDADE_TOKEN).timestamp()),
            "sub": contato,
        }
        assinado = f"{_json_base64url(_CABECALHO_JWT)}.{_json_base64url(claims)}"
        r, s = decode_dss_signature(
            self._privada.sign(assinado.encode(), ec.ECDSA(hashes.SHA256()))
        )
        assinatura = codificar(r.to_bytes(32, "big") + s.to_bytes(32, "big"))
        return f"vapid t={assinado}.{assinatura}, k={self.publica_base64url()}"
