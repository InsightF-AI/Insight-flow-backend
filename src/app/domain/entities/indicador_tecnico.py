from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from app.domain.enums.tipo_indicador import TipoIndicador


@dataclass
class IndicadorTecnico:
    id: UUID
    ativo_id: UUID
    tipo: TipoIndicador
    parametros: dict
    data_calculo: datetime
    valor: Decimal
    valores_auxiliares: dict | None = None
