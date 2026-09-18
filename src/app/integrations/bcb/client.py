from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

import httpx


class BcbIndisponivelError(Exception):
    pass


@dataclass
class PontoCdi:
    data: date
    valor: Decimal


class BcbClient:
    def __init__(self, http_client: httpx.Client):
        self._http_client = http_client

    def buscar_ptax_venda(self) -> Decimal:
        dados = self._get("/dados/serie/bcdata.sgs.1/dados/ultimos/1", {"formato": "json"})
        if not dados:
            raise BcbIndisponivelError
        return Decimal(dados[0]["valor"])

    def buscar_serie_cdi(self, inicio: date, fim: date) -> list[PontoCdi]:
        dados = self._get(
            "/dados/serie/bcdata.sgs.12/dados",
            {
                "dataInicial": inicio.strftime("%d/%m/%Y"),
                "dataFinal": fim.strftime("%d/%m/%Y"),
                "formato": "json",
            },
        )
        return [
            PontoCdi(
                data=datetime.strptime(item["data"], "%d/%m/%Y").replace(tzinfo=UTC).date(),
                valor=Decimal(item["valor"]),
            )
            for item in dados
        ]

    def _get(self, caminho: str, params: dict[str, str]) -> list[dict]:
        try:
            resposta = self._http_client.get(caminho, params=params)
            resposta.raise_for_status()
        except httpx.HTTPError as exc:
            raise BcbIndisponivelError from exc
        return resposta.json()
