from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class RefreshToken:
    id: UUID
    usuario_id: UUID
    token_hash: str
    familia_id: UUID
    criado_em: datetime
    expira_em: datetime
    revogado_em: datetime | None = None

    def esta_expirado(self, agora: datetime) -> bool:
        return agora >= self.expira_em

    def esta_revogado(self) -> bool:
        return self.revogado_em is not None

    def revogar(self, agora: datetime) -> None:
        self.revogado_em = agora
