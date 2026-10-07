from functools import lru_cache

from app.integrations.limitador import LimitadorTaxa


@lru_cache
def limitador_compartilhado(
    provedor: str, requisicoes_por_minuto: int, espera_maxima_segundos: float
) -> LimitadorTaxa:
    return LimitadorTaxa(requisicoes_por_minuto, espera_maxima_segundos)
