from __future__ import annotations

import logging

import redis

from app.services.mercado_cache import MercadoCache

logger = logging.getLogger(__name__)


class RedisMercadoCache(MercadoCache):
    def __init__(self, cliente: redis.Redis):
        self._cliente = cliente

    def obter(self, chave: str) -> str | None:
        try:
            valor = self._cliente.get(chave)
        except redis.RedisError:
            logger.warning("Redis indisponivel ao ler a chave %s; seguindo sem cache.", chave)
            return None
        return valor.decode("utf-8") if valor is not None else None

    def salvar(self, chave: str, valor: str, ttl_segundos: int) -> None:
        try:
            self._cliente.set(chave, valor, ex=ttl_segundos)
        except redis.RedisError:
            logger.warning("Redis indisponivel ao gravar a chave %s; cache nao atualizado.", chave)
