from __future__ import annotations

import json
import logging
import logging.config
import re
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from uuid import uuid4

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)

_PADRAO_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

_ATRIBUTOS_PADRAO = set(vars(logging.LogRecord("", logging.INFO, "", 0, "", (), None)).keys()) | {
    "message",
    "asctime",
    "correlation_id",
    "taskName",
}


def correlation_id_atual() -> str | None:
    return _correlation_id.get()


def id_de_correlacao_valido(valor: str) -> bool:
    return bool(_PADRAO_ID.fullmatch(valor))


def novo_correlation_id() -> str:
    return uuid4().hex


@contextmanager
def em_correlacao(correlation_id: str | None = None) -> Iterator[str]:
    valor = correlation_id or novo_correlation_id()
    token = _correlation_id.set(valor)
    try:
        yield valor
    finally:
        _correlation_id.reset(token)


_fabrica_original = logging.getLogRecordFactory()


def _criar_registro(*args, **kwargs) -> logging.LogRecord:
    registro = _fabrica_original(*args, **kwargs)
    registro.correlation_id = _correlation_id.get()
    return registro


logging.setLogRecordFactory(_criar_registro)


def _extras(record: logging.LogRecord) -> dict:
    return {chave: valor for chave, valor in vars(record).items() if chave not in _ATRIBUTOS_PADRAO}


class FormatadorJson(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        dados = {
            "timestamp": datetime.fromtimestamp(record.created, UTC)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "nivel": record.levelname,
            "logger": record.name,
            "mensagem": record.getMessage(),
            "correlation_id": getattr(record, "correlation_id", None),
            **_extras(record),
        }
        if record.exc_info:
            dados["excecao"] = self.formatException(record.exc_info)
        return json.dumps(dados, ensure_ascii=False, default=str)


class FormatadorTexto(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        horario = datetime.fromtimestamp(record.created, UTC).strftime("%H:%M:%S")
        extras = " ".join(f"{chave}={valor}" for chave, valor in _extras(record).items())
        linha = (
            f"{horario} {record.levelname:<7} [{getattr(record, 'correlation_id', None) or '-'}] "
            f"{record.name}: {record.getMessage()}"
        )
        if extras:
            linha = f"{linha} {extras}"
        if record.exc_info:
            linha = f"{linha}\n{self.formatException(record.exc_info)}"
        return linha


_FORMATADORES = {"json": FormatadorJson, "texto": FormatadorTexto}


def configurar_logs(nivel: str, formato: str) -> None:
    if formato not in _FORMATADORES:
        raise ValueError(f"Formato de log desconhecido: {formato}")
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"padrao": {"()": _FORMATADORES[formato]}},
            "handlers": {
                "stdout": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                    "formatter": "padrao",
                }
            },
            "root": {"level": nivel.upper(), "handlers": ["stdout"]},
            "loggers": {
                "uvicorn": {"handlers": [], "propagate": True},
                "uvicorn.error": {"handlers": [], "propagate": True},
                "uvicorn.access": {"handlers": [], "propagate": False},
                "httpx": {"level": "WARNING"},
                "httpcore": {"level": "WARNING"},
                "apscheduler": {"level": "WARNING"},
            },
        }
    )
    logging.getLogger("uvicorn.access").disabled = True
