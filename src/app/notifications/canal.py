from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities.notificacao import Notificacao
from app.notifications.barramento import BarramentoNotificacoes
from app.notifications.serializacao import notificacao_para_dict


class CanalNotificacao(ABC):
    @abstractmethod
    def entregar(self, notificacao: Notificacao) -> None: ...


class CanalTempoReal(CanalNotificacao):
    def __init__(self, barramento: BarramentoNotificacoes):
        self._barramento = barramento

    def entregar(self, notificacao: Notificacao) -> None:
        self._barramento.publicar(
            notificacao.usuario_id,
            {"tipo": "notificacao", "notificacao": notificacao_para_dict(notificacao)},
        )
