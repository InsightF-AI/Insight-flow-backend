from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from app.domain.entities.indicador_tecnico import IndicadorTecnico
from app.domain.enums.tipo_indicador import TipoIndicador


def test_cria_indicador_tecnico_com_parametros_e_valor_calculado():
    indicador = IndicadorTecnico(
        id=uuid4(),
        ativo_id=uuid4(),
        tipo=TipoIndicador.RSI,
        parametros={"periodo": 14},
        data_calculo=datetime(2026, 9, 8, 18, 0, 0),
        valor=Decimal("62.4"),
    )

    assert indicador.tipo is TipoIndicador.RSI
    assert indicador.parametros == {"periodo": 14}
    assert indicador.valores_auxiliares is None


def test_permite_valores_auxiliares_para_indicadores_com_multiplas_saidas():
    indicador = IndicadorTecnico(
        id=uuid4(),
        ativo_id=uuid4(),
        tipo=TipoIndicador.BOLLINGER,
        parametros={"periodo": 20, "desvios": 2},
        data_calculo=datetime(2026, 9, 8, 18, 0, 0),
        valor=Decimal("38.90"),
        valores_auxiliares={
            "banda_superior": Decimal("40.10"),
            "banda_inferior": Decimal("37.20"),
        },
    )

    assert indicador.valores_auxiliares["banda_superior"] == Decimal("40.10")
