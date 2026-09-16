from enum import Enum


class TipoNotificacao(str, Enum):
    SINAL_ATIVADO = "SINAL_ATIVADO"
    ALERTA_DISPARADO = "ALERTA_DISPARADO"
