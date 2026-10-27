import logging
import time
from collections.abc import Callable

from app.core.logs import em_correlacao
from app.core.metricas import registrar_job

logger = logging.getLogger(__name__)


def executar_job(nome: str, funcao: Callable[[], None]) -> None:
    with em_correlacao():
        inicio = time.perf_counter()
        logger.info("Job %s iniciado.", nome, extra={"evento": "job_iniciado", "job": nome})
        try:
            funcao()
        except Exception:
            registrar_job(nome, sucesso=False, duracao_segundos=time.perf_counter() - inicio)
            logger.exception(
                "Job %s falhou.",
                nome,
                extra={"evento": "job_falhou", "job": nome, "duracao_ms": _decorrido(inicio)},
            )
            return
        registrar_job(nome, sucesso=True, duracao_segundos=time.perf_counter() - inicio)
        logger.info(
            "Job %s concluido.",
            nome,
            extra={"evento": "job_concluido", "job": nome, "duracao_ms": _decorrido(inicio)},
        )


def _decorrido(inicio: float) -> float:
    return round((time.perf_counter() - inicio) * 1000, 1)
