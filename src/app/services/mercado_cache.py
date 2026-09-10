from __future__ import annotations

from abc import ABC, abstractmethod


class MercadoCache(ABC):
    @abstractmethod
    def obter(self, chave: str) -> str | None: ...

    @abstractmethod
    def salvar(self, chave: str, valor: str, ttl_segundos: int) -> None: ...
