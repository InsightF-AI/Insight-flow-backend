from enum import Enum


class TipoOperacao(str, Enum):
    COMPRA = "COMPRA"
    VENDA = "VENDA"
