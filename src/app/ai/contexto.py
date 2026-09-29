from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID


def serializar(valor: Any) -> Any:
    if is_dataclass(valor) and not isinstance(valor, type):
        return serializar(asdict(valor))
    if isinstance(valor, Enum):
        return valor.value
    if isinstance(valor, Decimal | UUID):
        return str(valor)
    if isinstance(valor, datetime | date):
        return valor.isoformat()
    if isinstance(valor, dict):
        return {_chave(chave): serializar(item) for chave, item in valor.items()}
    if isinstance(valor, list | tuple | set):
        return [serializar(item) for item in valor]
    return valor


def _chave(chave: Any) -> str:
    convertida = serializar(chave)
    return convertida if isinstance(convertida, str) else str(convertida)


def calcular_hash(contexto: dict) -> str:
    canonico = json.dumps(
        serializar(contexto), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()
