from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx

from app.integrations.limitador import LimitadorTaxa, LimiteTaxaExcedidoError
from app.integrations.retentativa import (
    POLITICA_PADRAO,
    PoliticaRetentativa,
    executar_com_retentativa,
)

TOKEN_NAO_REGISTRADO = "DeviceNotRegistered"

_CAMINHO_ENVIO = "/--/api/v2/push/send"
_CAMINHO_RECIBOS = "/--/api/v2/push/getReceipts"
_LOTE_ENVIO = 100
_LOTE_RECIBOS = 1000


def _so_falha_de_conexao(erro: httpx.TransportError) -> bool:
    return isinstance(erro, httpx.ConnectError)


@dataclass(frozen=True)
class ResultadoEnvio:
    token: str
    ticket_id: str | None
    erro: str | None


@dataclass(frozen=True)
class ReciboPush:
    status: str
    erro: str | None


class ExpoIndisponivelError(Exception):
    pass


def _erro_de(item: dict) -> str:
    detalhes = item.get("details")
    erro = detalhes.get("error") if isinstance(detalhes, dict) else None
    return erro or "desconhecido"


def _para_resultado(token: str, ticket: object) -> ResultadoEnvio:
    if not isinstance(ticket, dict):
        return ResultadoEnvio(token=token, ticket_id=None, erro="desconhecido")
    if ticket.get("status") == "ok" and ticket.get("id"):
        return ResultadoEnvio(token=token, ticket_id=str(ticket["id"]), erro=None)
    return ResultadoEnvio(token=token, ticket_id=None, erro=_erro_de(ticket))


class ExpoPushClient:
    def __init__(
        self,
        http_client: httpx.Client,
        access_token: str | None = None,
        limitador: LimitadorTaxa | None = None,
        politica: PoliticaRetentativa = POLITICA_PADRAO,
        dormir: Callable[[float], None] = time.sleep,
    ):
        self._http_client = http_client
        self._access_token = access_token
        self._limitador = limitador
        self._politica = politica
        self._dormir = dormir

    def enviar(self, mensagens: list[dict]) -> list[ResultadoEnvio]:
        resultados: list[ResultadoEnvio] = []
        for inicio in range(0, len(mensagens), _LOTE_ENVIO):
            lote = mensagens[inicio : inicio + _LOTE_ENVIO]
            dados = self._post(_CAMINHO_ENVIO, lote, _so_falha_de_conexao)
            tickets = dados.get("data")
            if not isinstance(tickets, list) or len(tickets) != len(lote):
                raise ExpoIndisponivelError("Resposta de envio inesperada da Expo")
            resultados.extend(
                _para_resultado(mensagem["to"], ticket)
                for mensagem, ticket in zip(lote, tickets, strict=True)
            )
        return resultados

    def buscar_recibos(self, ids: list[str]) -> dict[str, ReciboPush]:
        recibos: dict[str, ReciboPush] = {}
        for inicio in range(0, len(ids), _LOTE_RECIBOS):
            dados = self._post(_CAMINHO_RECIBOS, {"ids": ids[inicio : inicio + _LOTE_RECIBOS]})
            itens = dados.get("data")
            if not isinstance(itens, dict):
                raise ExpoIndisponivelError("Resposta de recibos inesperada da Expo")
            for ticket_id, recibo in itens.items():
                if not isinstance(recibo, dict):
                    continue
                status = str(recibo.get("status", "error"))
                recibos[ticket_id] = ReciboPush(
                    status=status, erro=None if status == "ok" else _erro_de(recibo)
                )
        return recibos

    def _post(
        self,
        caminho: str,
        corpo: object,
        retentar_falha_de_rede: Callable[[httpx.TransportError], bool] = lambda _: True,
    ) -> dict:
        headers = {"Accept": "application/json"}
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"

        def requisitar() -> httpx.Response:
            if self._limitador is not None:
                self._limitador.adquirir()
            return self._http_client.post(caminho, json=corpo, headers=headers)

        try:
            resposta = executar_com_retentativa(
                requisitar,
                self._politica,
                f"expo {caminho}",
                self._dormir,
                retentar_falha_de_rede=retentar_falha_de_rede,
            )
            resposta.raise_for_status()
            dados = resposta.json()
        except LimiteTaxaExcedidoError as exc:
            raise ExpoIndisponivelError("Limite de taxa da Expo") from exc
        except httpx.HTTPError as exc:
            raise ExpoIndisponivelError(str(exc)) from exc
        except ValueError as exc:
            raise ExpoIndisponivelError("Expo retornou corpo invalido") from exc

        if not isinstance(dados, dict):
            raise ExpoIndisponivelError("Expo retornou corpo inesperado")
        if dados.get("errors"):
            raise ExpoIndisponivelError(str(dados["errors"])[:200])
        return dados
