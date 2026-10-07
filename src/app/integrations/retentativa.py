from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PoliticaRetentativa:
    tentativas: int = 3
    backoff_base_segundos: float = 0.5
    espera_maxima_segundos: float = 10.0

    def __post_init__(self):
        if self.tentativas < 1:
            raise ValueError("tentativas deve ser maior que zero")


POLITICA_PADRAO = PoliticaRetentativa()


def _e_transitorio(resposta: httpx.Response) -> bool:
    return resposta.status_code == 429 or resposta.status_code >= 500


def _ler_retry_after(resposta: httpx.Response) -> float | None:
    valor = resposta.headers.get("Retry-After")
    if valor is None:
        return None
    try:
        return max(0.0, float(valor))
    except ValueError:
        return None


def executar_com_retentativa(
    requisicao: Callable[[], httpx.Response],
    politica: PoliticaRetentativa,
    descricao: str,
    dormir: Callable[[float], None] = time.sleep,
    aleatorio: Callable[[], float] = random.random,
    retentar_falha_de_rede: Callable[[httpx.TransportError], bool] = lambda _: True,
) -> httpx.Response:
    for tentativa in range(1, politica.tentativas):
        try:
            resposta = requisicao()
        except httpx.TransportError as exc:
            if not retentar_falha_de_rede(exc):
                raise
            motivo = type(exc).__name__
            espera = None
        else:
            if not _e_transitorio(resposta):
                return resposta
            motivo = f"HTTP {resposta.status_code}"
            espera = _ler_retry_after(resposta)
            if espera is not None and espera > politica.espera_maxima_segundos:
                logger.warning(
                    "%s: %s com Retry-After de %.0fs acima do teto; desistindo.",
                    descricao,
                    motivo,
                    espera,
                )
                return resposta

        if espera is None:
            exponencial = politica.backoff_base_segundos * 2 ** (tentativa - 1)
            espera = min(exponencial, politica.espera_maxima_segundos) * (0.5 + aleatorio() / 2)
        logger.warning(
            "%s: %s; tentativa %d de %d em %.1fs.",
            descricao,
            motivo,
            tentativa + 1,
            politica.tentativas,
            espera,
        )
        dormir(espera)

    return requisicao()
