from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class AnaliseIA:
    id: UUID
    ativo_id: UUID
    texto: str
    provedor: str
    modelo: str
    prompt_versao: str
    contexto_hash: str
    gerado_em: datetime
