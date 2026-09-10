from __future__ import annotations

from uuid import UUID

from app.domain.entities.cotacao import Cotacao
from app.repositories.interfaces.cotacao_repository import CotacaoRepository


class FakeCotacaoRepository(CotacaoRepository):
    def __init__(self) -> None:
        self._cotacoes: dict[tuple[UUID, object], Cotacao] = {}

    def salvar_muitas(self, cotacoes: list[Cotacao]) -> None:
        for cotacao in cotacoes:
            self._cotacoes[(cotacao.ativo_id, cotacao.data_hora)] = cotacao

    def listar_por_ativo(self, ativo_id: UUID) -> list[Cotacao]:
        return sorted(
            (c for c in self._cotacoes.values() if c.ativo_id == ativo_id),
            key=lambda c: c.data_hora,
        )
