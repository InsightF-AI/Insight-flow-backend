import anyio

from app.notifications.redis_barramento import _AssinaturaRedis


class _PubSubQuebrado:
    def __init__(self) -> None:
        self.fechado = False

    async def unsubscribe(self) -> None:
        raise ConnectionError("redis caiu")

    async def aclose(self) -> None:
        self.fechado = True


def test_fechar_com_redis_fora_libera_a_conexao_sem_propagar_erro():
    pubsub = _PubSubQuebrado()

    anyio.run(_AssinaturaRedis(pubsub).fechar)

    assert pubsub.fechado is True
