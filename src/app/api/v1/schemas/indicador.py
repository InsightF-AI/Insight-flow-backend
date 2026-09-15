from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.domain.entities.indicador_tecnico import IndicadorTecnico
from app.domain.enums.tipo_indicador import TipoIndicador


class IndicadorTecnicoResponse(BaseModel):
    tipo: TipoIndicador
    parametros: dict
    data_calculo: datetime
    valor: Decimal
    valores_auxiliares: dict | None

    @staticmethod
    def de(indicador: IndicadorTecnico) -> "IndicadorTecnicoResponse":
        return IndicadorTecnicoResponse(
            tipo=indicador.tipo,
            parametros=indicador.parametros,
            data_calculo=indicador.data_calculo,
            valor=indicador.valor,
            valores_auxiliares=indicador.valores_auxiliares,
        )
