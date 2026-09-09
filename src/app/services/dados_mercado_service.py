from __future__ import annotations

from app.integrations.brapi.client import AtivoEncontrado, BrapiClient


class DadosMercadoService:
    def __init__(self, brapi_client: BrapiClient):
        self._brapi_client = brapi_client

    def buscar_ativo(self, termo: str) -> list[AtivoEncontrado]:
        return self._brapi_client.buscar_ativos(termo)
