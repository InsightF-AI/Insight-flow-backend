import base64


def codificar(dados: bytes) -> str:
    return base64.urlsafe_b64encode(dados).rstrip(b"=").decode("ascii")


def decodificar(texto: str) -> bytes:
    preenchido = texto + "=" * (-len(texto) % 4)
    return base64.b64decode(preenchido.replace("-", "+").replace("_", "/"), validate=True)
