from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID


@dataclass
class Posicao:
    ativo_id: UUID
    ticker: str
    quantidade: Decimal
    preco_medio: Decimal
    cotacao_atual: Decimal
    valor_mercado: Decimal
    valor_mercado_brl: Decimal
    lucro_nao_realizado: Decimal
    lucro_realizado: Decimal
