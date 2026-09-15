from enum import Enum


class PeriodoHistorico(str, Enum):
    UM_DIA = "1D"
    UMA_SEMANA = "1S"
    UM_MES = "1M"
    TRES_MESES = "3M"
    UM_ANO = "1A"
    CINCO_ANOS = "5A"
