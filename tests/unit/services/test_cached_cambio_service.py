from decimal import Decimal

import pytest

from app.integrations.bcb.client import BcbIndisponivelError
from app.services.cached_cambio_service import CachedCambioService
from tests.fixtures.fake_cambio_service import FakeCambioService
from tests.fixtures.fake_mercado_cache import FakeMercadoCache

_TTL = 21600
_TTL_FALLBACK = 2592000


def _service(interno=None, cache=None) -> CachedCambioService:
    return CachedCambioService(
        interno or FakeCambioService(),
        cache or FakeMercadoCache(),
        ttl_segundos=_TTL,
        ttl_fallback_segundos=_TTL_FALLBACK,
    )


def test_cache_vazio_busca_no_interno_e_povoa_as_duas_chaves():
    interno = FakeCambioService(taxa=Decimal("5.00"))
    cache = FakeMercadoCache()
    service = _service(interno, cache)

    resultado = service.obter_taxa("USD", "BRL")

    assert resultado == Decimal("5.00")
    assert cache.obter("cambio:USD_BRL") == "5.00"
    assert cache.obter("cambio:USD_BRL:fallback") == "5.00"
    assert cache.ttls["cambio:USD_BRL"] == _TTL
    assert cache.ttls["cambio:USD_BRL:fallback"] == _TTL_FALLBACK


def test_cache_populado_nao_chama_o_interno():
    interno = FakeCambioService(taxa=Decimal("5.00"))
    cache = FakeMercadoCache()
    service = _service(interno, cache)
    service.obter_taxa("USD", "BRL")
    interno.indisponivel = True

    resultado = service.obter_taxa("USD", "BRL")

    assert resultado == Decimal("5.00")


def test_cache_curto_expirado_com_interno_indisponivel_usa_fallback():
    interno = FakeCambioService(taxa=Decimal("5.00"))
    cache = FakeMercadoCache()
    service = _service(interno, cache)
    service.obter_taxa("USD", "BRL")
    del cache._valores["cambio:USD_BRL"]
    interno.indisponivel = True

    resultado = service.obter_taxa("USD", "BRL")

    assert resultado == Decimal("5.00")


def test_sem_cache_e_interno_indisponivel_propaga_o_erro():
    interno = FakeCambioService(indisponivel=True)
    cache = FakeMercadoCache()
    service = _service(interno, cache)

    with pytest.raises(BcbIndisponivelError):
        service.obter_taxa("USD", "BRL")


def test_converter_e_herdado_e_usa_obter_taxa_da_subclasse():
    interno = FakeCambioService(taxa=Decimal("5.00"))
    cache = FakeMercadoCache()
    service = _service(interno, cache)

    resultado = service.converter(Decimal("10"), "USD", "BRL")

    assert resultado == Decimal("50.00")
