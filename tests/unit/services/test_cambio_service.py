from decimal import Decimal

import pytest

from app.integrations.bcb.client import BcbIndisponivelError
from app.services.cambio_service import MOEDAS_SUPORTADAS, BcbCambioService
from app.services.exceptions import MoedaNaoSuportadaError


class _BcbClientFalso:
    def __init__(self, ptax: Decimal | None = None, indisponivel: bool = False):
        self._ptax = ptax
        self._indisponivel = indisponivel
        self.chamadas = 0

    def buscar_ptax_venda(self) -> Decimal:
        self.chamadas += 1
        if self._indisponivel:
            raise BcbIndisponivelError
        return self._ptax


def test_moedas_suportadas_e_brl_e_usd():
    assert MOEDAS_SUPORTADAS == {"BRL", "USD"}


def test_converter_com_mesma_moeda_retorna_o_valor_sem_chamar_o_client():
    bcb_client = _BcbClientFalso(ptax=Decimal("5.00"))
    service = BcbCambioService(bcb_client)

    resultado = service.converter(Decimal("100"), "BRL", "BRL")

    assert resultado == Decimal("100")
    assert bcb_client.chamadas == 0


def test_converter_usd_para_brl_multiplica_pela_ptax():
    bcb_client = _BcbClientFalso(ptax=Decimal("5.00"))
    service = BcbCambioService(bcb_client)

    resultado = service.converter(Decimal("10"), "USD", "BRL")

    assert resultado == Decimal("50.00")


def test_converter_brl_para_usd_divide_pela_ptax():
    bcb_client = _BcbClientFalso(ptax=Decimal("5.00"))
    service = BcbCambioService(bcb_client)

    resultado = service.converter(Decimal("50"), "BRL", "USD")

    assert resultado == Decimal("10")


def test_obter_taxa_com_par_nao_suportado_lanca_moeda_nao_suportada():
    bcb_client = _BcbClientFalso(ptax=Decimal("5.00"))
    service = BcbCambioService(bcb_client)

    with pytest.raises(MoedaNaoSuportadaError):
        service.obter_taxa("EUR", "BRL")


def test_converter_propaga_bcb_indisponivel():
    bcb_client = _BcbClientFalso(indisponivel=True)
    service = BcbCambioService(bcb_client)

    with pytest.raises(BcbIndisponivelError):
        service.converter(Decimal("10"), "USD", "BRL")
