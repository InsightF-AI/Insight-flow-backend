from __future__ import annotations

from decimal import Decimal

import httpx


class BcbIndisponivelError(Exception):
    pass


class BcbClient:
    def __init__(self, http_client: httpx.Client):
        self._http_client = http_client

    def buscar_ptax_venda(self) -> Decimal:
        dados = self._get("/dados/serie/bcdata.sgs.1/dados/ultimos/1", {"formato": "json"})
        if not dados:
            raise BcbIndisponivelError
        return Decimal(dados[0]["valor"])

    def _get(self, caminho: str, params: dict[str, str]) -> list[dict]:
        try:
            resposta = self._http_client.get(caminho, params=params)
            resposta.raise_for_status()
        except httpx.HTTPError as exc:
            raise BcbIndisponivelError from exc
        return resposta.json()
