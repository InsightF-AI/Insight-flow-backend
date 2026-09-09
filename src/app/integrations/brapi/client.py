from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.domain.enums.tipo_ativo import TipoAtivo

_MAPA_SUBTYPE: dict[str, TipoAtivo] = {
    "stock": TipoAtivo.ACAO,
    "fii": TipoAtivo.FII,
    "etf": TipoAtivo.ETF,
    "bdr": TipoAtivo.BDR,
}


class BrapiIndisponivelError(Exception):
    pass


@dataclass
class AtivoEncontrado:
    ticker: str
    nome: str
    tipo: TipoAtivo
    moeda: str
    setor: str | None


class BrapiClient:
    def __init__(self, http_client: httpx.Client, api_key: str | None = None):
        self._http_client = http_client
        self._api_key = api_key

    def buscar_ativos(self, termo: str) -> list[AtivoEncontrado]:
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        try:
            resposta = self._http_client.get(
                "/api/v2/tickers", params={"search": termo}, headers=headers
            )
            resposta.raise_for_status()
        except httpx.HTTPError as exc:
            raise BrapiIndisponivelError from exc

        dados = resposta.json()
        resultado = []
        for item in dados.get("results", []):
            tipo = _MAPA_SUBTYPE.get(item.get("subType"))
            if tipo is None:
                continue
            resultado.append(
                AtivoEncontrado(
                    ticker=item["symbol"],
                    nome=item["name"],
                    tipo=tipo,
                    moeda=item["currency"],
                    setor=item.get("sector"),
                )
            )
        return resultado
