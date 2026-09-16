from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.alerta_personalizado import AlertaPersonalizado


class AlertaRepository(ABC):
    @abstractmethod
    def salvar(self, alerta: AlertaPersonalizado) -> None: ...

    @abstractmethod
    def buscar_por_id(self, alerta_id: UUID) -> AlertaPersonalizado | None: ...

    @abstractmethod
    def listar_por_usuario(self, usuario_id: UUID) -> list[AlertaPersonalizado]: ...

    @abstractmethod
    def listar_ativos_por_ativo(self, ativo_id: UUID) -> list[AlertaPersonalizado]: ...

    @abstractmethod
    def remover(self, alerta: AlertaPersonalizado) -> None: ...

    @abstractmethod
    def listar_ativos_distintos_com_alerta_ativo(self) -> list[UUID]: ...
