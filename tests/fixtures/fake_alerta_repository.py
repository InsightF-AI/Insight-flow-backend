from __future__ import annotations

from uuid import UUID

from app.domain.entities.alerta_personalizado import AlertaPersonalizado
from app.repositories.interfaces.alerta_repository import AlertaRepository


class FakeAlertaRepository(AlertaRepository):
    def __init__(self) -> None:
        self._alertas: dict[UUID, AlertaPersonalizado] = {}

    def salvar(self, alerta: AlertaPersonalizado) -> None:
        self._alertas[alerta.id] = alerta

    def buscar_por_id(self, alerta_id: UUID) -> AlertaPersonalizado | None:
        return self._alertas.get(alerta_id)

    def listar_por_usuario(self, usuario_id: UUID) -> list[AlertaPersonalizado]:
        return [alerta for alerta in self._alertas.values() if alerta.usuario_id == usuario_id]

    def listar_ativos_por_ativo(self, ativo_id: UUID) -> list[AlertaPersonalizado]:
        return [
            alerta
            for alerta in self._alertas.values()
            if alerta.ativo_id == ativo_id and alerta.ativo
        ]

    def remover(self, alerta: AlertaPersonalizado) -> None:
        self._alertas.pop(alerta.id, None)

    def listar_ativos_distintos_com_alerta_ativo(self) -> list[UUID]:
        return list({alerta.ativo_id for alerta in self._alertas.values() if alerta.ativo})
