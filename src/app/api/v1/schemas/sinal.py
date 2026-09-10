from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from app.domain.entities.regra_sinal import RegraSinal
from app.domain.entities.sinal import Sinal
from app.domain.value_objects.resultado_backtest import ResultadoBacktest


class SinalResponse(BaseModel):
    id: UUID
    ativo_id: UUID
    regra_id: UUID
    regra_nome: str
    regra_descricao: str
    data_ativacao: datetime
    contexto: dict
    data_desativacao: datetime | None

    @staticmethod
    def de(sinal: Sinal, regra: RegraSinal) -> "SinalResponse":
        return SinalResponse(
            id=sinal.id,
            ativo_id=sinal.ativo_id,
            regra_id=sinal.regra_id,
            regra_nome=regra.nome,
            regra_descricao=regra.descricao,
            data_ativacao=sinal.data_ativacao,
            contexto=sinal.contexto,
            data_desativacao=sinal.data_desativacao,
        )


class ResultadoBacktestResponse(BaseModel):
    regra_id: UUID
    ativo_id: UUID
    total_ocorrencias: int
    retorno_medio_5_pregoes: Decimal | None
    retorno_medio_20_pregoes: Decimal | None
    retorno_medio_60_pregoes: Decimal | None

    @staticmethod
    def de(resultado: ResultadoBacktest) -> "ResultadoBacktestResponse":
        return ResultadoBacktestResponse(
            regra_id=resultado.regra_id,
            ativo_id=resultado.ativo_id,
            total_ocorrencias=resultado.total_ocorrencias,
            retorno_medio_5_pregoes=resultado.retorno_medio_5_pregoes,
            retorno_medio_20_pregoes=resultado.retorno_medio_20_pregoes,
            retorno_medio_60_pregoes=resultado.retorno_medio_60_pregoes,
        )
