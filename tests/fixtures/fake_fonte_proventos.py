from __future__ import annotations

from app.domain.value_objects.provento import Provento
from app.integrations.erros import TickerNaoEncontradoError


class FakeFonteProventos:
    def __init__(self, proventos: dict[str, list[Provento]] | None = None) -> None:
        self.proventos: dict[str, list[Provento]] = proventos or {}
        self.consultas: list[str] = []
        self.erro: Exception | None = None

    def buscar_proventos(self, ticker: str) -> list[Provento]:
        self.consultas.append(ticker)
        if self.erro is not None:
            raise self.erro
        if ticker not in self.proventos:
            raise TickerNaoEncontradoError(ticker)
        return list(self.proventos[ticker])
