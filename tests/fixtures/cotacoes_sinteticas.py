from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from app.domain.entities.cotacao import Cotacao

_INICIO_PADRAO = datetime(2026, 1, 1, tzinfo=UTC)


def gerar_cotacoes(
    ativo_id: UUID, quantidade: int = 60, inicio: datetime = _INICIO_PADRAO
) -> list[Cotacao]:
    cotacoes = []
    for indice in range(quantidade):
        preco = Decimal(20 + (indice * 3) % 11)
        cotacoes.append(
            Cotacao(
                id=uuid4(),
                ativo_id=ativo_id,
                data_hora=inicio + timedelta(days=indice),
                abertura=preco,
                maxima=preco,
                minima=preco,
                fechamento=preco,
                volume=Decimal(1000000 + indice * 1000),
            )
        )
    return cotacoes
