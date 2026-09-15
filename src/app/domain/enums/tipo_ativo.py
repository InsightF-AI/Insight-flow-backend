from enum import Enum


class TipoAtivo(str, Enum):
    ACAO = "ACAO"
    FII = "FII"
    ETF = "ETF"
    BDR = "BDR"
    CRIPTO = "CRIPTO"
