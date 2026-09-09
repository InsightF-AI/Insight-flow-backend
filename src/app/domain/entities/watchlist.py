from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class Watchlist:
    id: UUID
    usuario_id: UUID
    ativo_id: UUID
    adicionado_em: datetime
    notificar: bool = True

    @staticmethod
    def adicionar(id: UUID, usuario_id: UUID, ativo_id: UUID, adicionado_em: datetime) -> Watchlist:
        return Watchlist(
            id=id,
            usuario_id=usuario_id,
            ativo_id=ativo_id,
            adicionado_em=adicionado_em,
            notificar=True,
        )

    def desabilitar_notificacao(self) -> None:
        self.notificar = False

    def habilitar_notificacao(self) -> None:
        self.notificar = True
