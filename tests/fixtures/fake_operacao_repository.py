from __future__ import annotations

from uuid import UUID

from app.domain.entities.operacao import Operacao
from app.repositories.interfaces.operacao_repository import OperacaoRepository


class FakeOperacaoRepository(OperacaoRepository):
    def __init__(self) -> None:
        self._operacoes: dict[UUID, Operacao] = {}

    def salvar(self, operacao: Operacao) -> None:
        self._operacoes[operacao.id] = operacao

    def buscar_por_id(self, operacao_id: UUID) -> Operacao | None:
        return self._operacoes.get(operacao_id)

    def listar_por_usuario(self, usuario_id: UUID) -> list[Operacao]:
        return [op for op in self._operacoes.values() if op.usuario_id == usuario_id]

    def remover(self, operacao: Operacao) -> None:
        self._operacoes.pop(operacao.id, None)
