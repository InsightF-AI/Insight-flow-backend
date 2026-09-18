from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.entities.operacao import Operacao
from app.domain.enums.tipo_operacao import TipoOperacao
from app.services.exceptions import QuantidadeInsuficienteError


@dataclass
class EstadoPosicao:
    quantidade: Decimal = Decimal(0)
    preco_medio: Decimal = Decimal(0)
    lucro_realizado: Decimal = Decimal(0)


def replay_operacoes(operacoes: list[Operacao]) -> EstadoPosicao:
    estado = EstadoPosicao()
    for op in sorted(operacoes, key=lambda o: (o.data, o.criado_em)):
        if op.tipo == TipoOperacao.COMPRA:
            custo_total = estado.quantidade * estado.preco_medio + op.valor_total()
            estado.quantidade += op.quantidade
            estado.preco_medio = custo_total / estado.quantidade
        else:
            if op.quantidade > estado.quantidade:
                raise QuantidadeInsuficienteError(op.ativo_id)
            estado.lucro_realizado += (op.preco_unitario - estado.preco_medio) * op.quantidade
            estado.quantidade -= op.quantidade
            if estado.quantidade == 0:
                estado.preco_medio = Decimal(0)
    return estado
