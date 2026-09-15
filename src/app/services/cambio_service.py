from __future__ import annotations

from decimal import Decimal

from app.integrations.bcb.client import BcbClient
from app.services.exceptions import MoedaNaoSuportadaError

MOEDAS_SUPORTADAS = {"BRL", "USD"}


class CambioService:
    def obter_taxa(self, de: str, para: str) -> Decimal:
        raise NotImplementedError

    def converter(self, valor: Decimal, de: str, para: str) -> Decimal:
        if de == para:
            return valor
        return valor * self.obter_taxa(de, para)


class BcbCambioService(CambioService):
    def __init__(self, bcb_client: BcbClient):
        self._bcb_client = bcb_client

    def obter_taxa(self, de: str, para: str) -> Decimal:
        if de not in MOEDAS_SUPORTADAS or para not in MOEDAS_SUPORTADAS:
            raise MoedaNaoSuportadaError(f"{de}->{para}")

        ptax = self._bcb_client.buscar_ptax_venda()
        if de == "USD" and para == "BRL":
            return ptax
        if de == "BRL" and para == "USD":
            return Decimal(1) / ptax
        raise MoedaNaoSuportadaError(f"{de}->{para}")
