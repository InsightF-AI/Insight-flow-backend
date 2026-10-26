from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from app.domain.value_objects.provento import Provento, ProventoRecebido, ResumoProventos


class ProventoResponse(BaseModel):
    data_ex: date
    valor_por_cota: Decimal

    @staticmethod
    def de(provento: Provento) -> "ProventoResponse":
        return ProventoResponse(data_ex=provento.data_ex, valor_por_cota=provento.valor_por_cota)


class ProventoRecebidoResponse(BaseModel):
    ativo_id: UUID
    ticker: str
    data_ex: date
    valor_por_cota: Decimal
    quantidade: Decimal
    total_brl: Decimal

    @staticmethod
    def de(provento: ProventoRecebido) -> "ProventoRecebidoResponse":
        return ProventoRecebidoResponse(
            ativo_id=provento.ativo_id,
            ticker=provento.ticker,
            data_ex=provento.data_ex,
            valor_por_cota=provento.valor_por_cota,
            quantidade=provento.quantidade,
            total_brl=provento.total_brl,
        )


class ResumoProventosResponse(BaseModel):
    total_brl: Decimal
    proventos: list[ProventoRecebidoResponse]

    @staticmethod
    def de(resumo: ResumoProventos) -> "ResumoProventosResponse":
        return ResumoProventosResponse(
            total_brl=resumo.total_brl,
            proventos=[ProventoRecebidoResponse.de(p) for p in resumo.proventos],
        )
