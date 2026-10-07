import asyncio
import os
from uuid import uuid4

import pytest
import redis
import redis.asyncio

from app.notifications.redis_barramento import RedisBarramentoNotificacoes

pytestmark = pytest.mark.integration

TEST_REDIS_URL = os.getenv("TEST_REDIS_URL", "redis://localhost:6381/1")


def _barramento() -> RedisBarramentoNotificacoes:
    return RedisBarramentoNotificacoes(
        redis.Redis.from_url(TEST_REDIS_URL), redis.asyncio.Redis.from_url(TEST_REDIS_URL)
    )


def test_publicar_entrega_o_payload_a_quem_assinou_o_usuario():
    async def cenario():
        barramento = _barramento()
        usuario_id = uuid4()
        assinatura = await barramento.assinar(usuario_id)
        await asyncio.to_thread(barramento.publicar, usuario_id, {"tipo": "notificacao", "n": 1})
        recebido = await asyncio.wait_for(assinatura.proxima(), timeout=2)
        await assinatura.fechar()
        return recebido

    assert asyncio.run(cenario()) == {"tipo": "notificacao", "n": 1}


def test_assinante_de_outro_usuario_nao_recebe():
    async def cenario():
        barramento = _barramento()
        assinatura = await barramento.assinar(uuid4())
        await asyncio.to_thread(barramento.publicar, uuid4(), {"tipo": "notificacao"})
        try:
            await asyncio.wait_for(assinatura.proxima(), timeout=0.5)
            return "recebeu"
        except TimeoutError:
            return "nada"
        finally:
            await assinatura.fechar()

    assert asyncio.run(cenario()) == "nada"
