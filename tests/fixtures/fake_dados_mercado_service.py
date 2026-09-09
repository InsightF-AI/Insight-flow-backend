from __future__ import annotations

from app.integrations.brapi.client import AtivoEncontrado, BrapiIndisponivelError
from app.services.dados_mercado_service import DadosMercadoService


class FakeDadosMercadoService(DadosMercadoService):
    def __init__(self, catalogo: list[AtivoEncontrado] | None = None, indisponivel: bool = False):
        self._catalogo = catalogo if catalogo is not None else []
        self.indisponivel = indisponivel

    def buscar_ativo(self, termo: str) -> list[AtivoEncontrado]:
        if self.indisponivel:
            raise BrapiIndisponivelError

        termo_normalizado = termo.lower()
        return [
            ativo
            for ativo in self._catalogo
            if termo_normalizado in ativo.ticker.lower() or termo_normalizado in ativo.nome.lower()
        ]
