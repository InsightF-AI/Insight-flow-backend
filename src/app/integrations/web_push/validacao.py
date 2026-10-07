from __future__ import annotations

from urllib.parse import urlsplit

from cryptography.hazmat.primitives.asymmetric import ec

from app.integrations.web_push.base64url import decodificar

HOSTS_PERMITIDOS_PADRAO = [
    "fcm.googleapis.com",
    "updates.push.services.mozilla.com",
    "*.push.apple.com",
    "*.notify.windows.com",
]

_TAMANHO_MAXIMO_ENDPOINT = 1024


class InscricaoWebPushInvalidaError(Exception):
    pass


def _host_permitido(host: str, hosts_permitidos: list[str]) -> bool:
    for padrao in hosts_permitidos:
        padrao = padrao.lower()
        if padrao.startswith("*."):
            if host.endswith(padrao[1:]) and host != padrao[2:]:
                return True
        elif host == padrao:
            return True
    return False


def _validar_endpoint(endpoint: str, hosts_permitidos: list[str]) -> None:
    if len(endpoint) > _TAMANHO_MAXIMO_ENDPOINT:
        raise InscricaoWebPushInvalidaError
    url = urlsplit(endpoint)
    if url.scheme != "https" or url.username or url.password or not url.hostname:
        raise InscricaoWebPushInvalidaError
    try:
        porta = url.port
    except ValueError as exc:
        raise InscricaoWebPushInvalidaError from exc
    if porta is not None and porta != 443:
        raise InscricaoWebPushInvalidaError
    if not _host_permitido(url.hostname.lower(), hosts_permitidos):
        raise InscricaoWebPushInvalidaError


def _decodificar(valor: str) -> bytes:
    try:
        return decodificar(valor)
    except ValueError as exc:
        raise InscricaoWebPushInvalidaError from exc


def validar_inscricao(endpoint: str, p256dh: str, auth: str, hosts_permitidos: list[str]) -> None:
    _validar_endpoint(endpoint, hosts_permitidos)

    chave = _decodificar(p256dh)
    if len(chave) != 65 or chave[0] != 0x04:
        raise InscricaoWebPushInvalidaError
    try:
        ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), chave)
    except ValueError as exc:
        raise InscricaoWebPushInvalidaError from exc

    if len(_decodificar(auth)) != 16:
        raise InscricaoWebPushInvalidaError
