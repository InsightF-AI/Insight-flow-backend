from __future__ import annotations

import logging
from decimal import Decimal

from app.integrations.bcb.client import BcbIndisponivelError
from app.services.cambio_service import CambioService
from app.services.mercado_cache import MercadoCache

logger = logging.getLogger(__name__)


class CachedCambioService(CambioService):
    def __init__(
        self,
        interno: CambioService,
        cache: MercadoCache,
        ttl_segundos: int,
        ttl_fallback_segundos: int,
    ):
        self._interno = interno
        self._cache = cache
        self._ttl_segundos = ttl_segundos
        self._ttl_fallback_segundos = ttl_fallback_segundos

    def obter_taxa(self, de: str, para: str) -> Decimal:
        chave = f"cambio:{de}_{para}"
        em_cache = self._cache.obter(chave)
        if em_cache is not None:
            return Decimal(em_cache)

        chave_fallback = f"{chave}:fallback"
        try:
            taxa = self._interno.obter_taxa(de, para)
        except BcbIndisponivelError:
            fallback = self._cache.obter(chave_fallback)
            if fallback is not None:
                logger.warning("BCB indisponivel; usando ultima taxa conhecida para %s.", chave)
                return Decimal(fallback)
            raise

        self._cache.salvar(chave, str(taxa), self._ttl_segundos)
        self._cache.salvar(chave_fallback, str(taxa), self._ttl_fallback_segundos)
        return taxa
