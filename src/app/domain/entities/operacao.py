from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from app.domain.enums.tipo_operacao import TipoOperacao


@dataclass
class Operacao:
    id: UUID
    usuario_id: UUID
    ativo_id: UUID
    tipo: TipoOperacao
    quantidade: Decimal
    preco_unitario: Decimal
    data: date
    criado_em: datetime

    def valor_total(self) -> Decimal:
        return self.quantidade * self.preco_unitario
