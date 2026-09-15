from __future__ import annotations

from decimal import Decimal

from app.integrations.bcb.client import BcbIndisponivelError
from app.services.cambio_service import CambioService


class FakeCambioService(CambioService):
    def __init__(self, taxa: Decimal | None = None, indisponivel: bool = False):
        self._taxa = taxa
        self.indisponivel = indisponivel
        self.chamadas = 0

    def obter_taxa(self, de: str, para: str) -> Decimal:
        self.chamadas += 1
        if self.indisponivel:
            raise BcbIndisponivelError
        return self._taxa
