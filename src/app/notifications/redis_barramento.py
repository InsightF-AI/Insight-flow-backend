from __future__ import annotations

import contextlib
import json
from uuid import UUID

import redis
import redis.asyncio

from app.notifications.barramento import Assinatura, BarramentoNotificacoes


def _canal(usuario_id: UUID) -> str:
    return f"notificacoes:{usuario_id}"


class _AssinaturaRedis(Assinatura):
    def __init__(self, pubsub: redis.asyncio.client.PubSub):
        self._pubsub = pubsub

    async def proxima(self) -> dict:
        while True:
            mensagem = await self._pubsub.get_message(ignore_subscribe_messages=True, timeout=None)
            if mensagem is not None and mensagem.get("type") == "message":
                return json.loads(mensagem["data"])

    async def fechar(self) -> None:
        with contextlib.suppress(Exception):
            await self._pubsub.unsubscribe()
        with contextlib.suppress(Exception):
            await self._pubsub.aclose()


class RedisBarramentoNotificacoes(BarramentoNotificacoes):
    def __init__(self, redis_sync: redis.Redis, redis_async: redis.asyncio.Redis):
        self._redis_sync = redis_sync
        self._redis_async = redis_async

    def publicar(self, usuario_id: UUID, payload: dict) -> None:
        self._redis_sync.publish(_canal(usuario_id), json.dumps(payload))

    async def assinar(self, usuario_id: UUID) -> Assinatura:
        pubsub = self._redis_async.pubsub()
        await pubsub.subscribe(_canal(usuario_id))
        return _AssinaturaRedis(pubsub)
