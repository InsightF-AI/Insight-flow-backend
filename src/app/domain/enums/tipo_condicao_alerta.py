from enum import Enum


class TipoCondicaoAlerta(str, Enum):
    PRECO_MAIOR_IGUAL = "PRECO_MAIOR_IGUAL"
    PRECO_MENOR_IGUAL = "PRECO_MENOR_IGUAL"
