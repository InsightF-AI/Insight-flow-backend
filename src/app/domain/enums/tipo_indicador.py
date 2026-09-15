from enum import Enum


class TipoIndicador(str, Enum):
    SMA = "SMA"
    RSI = "RSI"
    MACD = "MACD"
    BOLLINGER = "BOLLINGER"
    VOLUME_RELATIVO = "VOLUME_RELATIVO"
