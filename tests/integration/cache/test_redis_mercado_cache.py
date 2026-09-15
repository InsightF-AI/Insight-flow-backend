import os
import time

import pytest
import redis

from app.services.redis_mercado_cache import RedisMercadoCache

pytestmark = pytest.mark.integration

TEST_REDIS_URL = os.getenv("TEST_REDIS_URL", "redis://localhost:6381/1")


@pytest.fixture
def cliente_redis():
    cliente = redis.Redis.from_url(TEST_REDIS_URL)
    cliente.flushdb()
    yield cliente
    cliente.flushdb()
    cliente.close()


def test_salvar_e_obter_retorna_o_mesmo_valor(cliente_redis):
    cache = RedisMercadoCache(cliente_redis)

    cache.salvar("chave", "valor", ttl_segundos=60)

    assert cache.obter("chave") == "valor"


def test_obter_chave_inexistente_retorna_none(cliente_redis):
    cache = RedisMercadoCache(cliente_redis)

    assert cache.obter("nao-existe") is None


def test_salvar_respeita_o_ttl(cliente_redis):
    cache = RedisMercadoCache(cliente_redis)

    cache.salvar("chave", "valor", ttl_segundos=1)
    time.sleep(1.2)

    assert cache.obter("chave") is None


def test_obter_com_redis_indisponivel_retorna_none_em_vez_de_propagar():
    cliente_inalcancavel = redis.Redis(host="localhost", port=1, socket_connect_timeout=0.2)
    cache = RedisMercadoCache(cliente_inalcancavel)

    assert cache.obter("qualquer") is None


def test_salvar_com_redis_indisponivel_nao_propaga_erro():
    cliente_inalcancavel = redis.Redis(host="localhost", port=1, socket_connect_timeout=0.2)
    cache = RedisMercadoCache(cliente_inalcancavel)

    cache.salvar("qualquer", "valor", ttl_segundos=60)
