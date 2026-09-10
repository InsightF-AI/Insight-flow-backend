from __future__ import annotations

from app.services.mercado_cache import MercadoCache


class FakeMercadoCache(MercadoCache):
    def __init__(self) -> None:
        self._valores: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    def obter(self, chave: str) -> str | None:
        return self._valores.get(chave)

    def salvar(self, chave: str, valor: str, ttl_segundos: int) -> None:
        self._valores[chave] = valor
        self.ttls[chave] = ttl_segundos
