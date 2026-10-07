import logging
from datetime import UTC, datetime
from uuid import uuid4

from app.domain.entities.inscricao_web_push import InscricaoWebPush
from app.domain.entities.notificacao import Notificacao
from app.domain.enums.tipo_notificacao import TipoNotificacao
from app.integrations.web_push.client import ResultadoWebPush, WebPushIndisponivelError
from app.notifications.canal_web_push import CanalWebPush
from tests.fixtures.fake_inscricao_web_push_repository import FakeInscricaoWebPushRepository

_AGORA = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)


class _ClienteFalso:
    def __init__(self, resultados: dict[str, object] | None = None):
        self.enviados: list[tuple[str, dict]] = []
        self._resultados = resultados or {}

    def enviar(self, endpoint: str, p256dh: str, auth: str, payload: dict) -> ResultadoWebPush:
        self.enviados.append((endpoint, payload))
        resultado = self._resultados.get(endpoint, ResultadoWebPush.ENTREGUE)
        if isinstance(resultado, Exception):
            raise resultado
        return resultado


def _cenario(*endpoints: str, cliente: _ClienteFalso | None = None):
    usuario_id = uuid4()
    repositorio = FakeInscricaoWebPushRepository()
    for endpoint in endpoints:
        repositorio.salvar(
            InscricaoWebPush(
                id=uuid4(),
                usuario_id=usuario_id,
                endpoint=endpoint,
                p256dh="p",
                auth="a",
                criado_em=_AGORA,
                atualizado_em=_AGORA,
            )
        )
    cliente = cliente or _ClienteFalso()
    return CanalWebPush(repositorio, cliente), usuario_id, repositorio, cliente


def _notificacao(usuario_id) -> Notificacao:
    return Notificacao(
        id=uuid4(),
        usuario_id=usuario_id,
        ativo_id=None,
        tipo=TipoNotificacao.ALERTA_DISPARADO,
        mensagem="PETR4 atingiu o alvo",
        contexto={},
        criado_em=_AGORA,
    )


def test_sem_inscricoes_nao_envia():
    canal, usuario_id, _, cliente = _cenario()

    canal.entregar(_notificacao(usuario_id))

    assert cliente.enviados == []


def test_envia_o_payload_comum_para_cada_inscricao():
    canal, usuario_id, _, cliente = _cenario("https://a/1", "https://a/2")
    notificacao = _notificacao(usuario_id)

    canal.entregar(notificacao)

    assert [e for e, _ in cliente.enviados] == ["https://a/1", "https://a/2"]
    assert cliente.enviados[0][1]["title"] == "Alerta de preço"
    assert cliente.enviados[0][1]["data"]["notificacao_id"] == str(notificacao.id)


def test_inscricao_expirada_e_apagada():
    cliente = _ClienteFalso({"https://a/1": ResultadoWebPush.INSCRICAO_EXPIRADA})
    canal, usuario_id, repositorio, _ = _cenario("https://a/1", "https://a/2", cliente=cliente)

    canal.entregar(_notificacao(usuario_id))

    assert [i.endpoint for i in repositorio.listar_todos()] == ["https://a/2"]


def test_falha_numa_inscricao_nao_impede_as_outras():
    cliente = _ClienteFalso({"https://a/1": WebPushIndisponivelError("HTTP 503")})
    canal, usuario_id, repositorio, _ = _cenario("https://a/1", "https://a/2", cliente=cliente)

    canal.entregar(_notificacao(usuario_id))

    assert [e for e, _ in cliente.enviados] == ["https://a/1", "https://a/2"]
    assert len(repositorio.listar_todos()) == 2


def test_loga_resumo_sem_endpoint(caplog):
    cliente = _ClienteFalso(
        {
            "https://a/1": ResultadoWebPush.INSCRICAO_EXPIRADA,
            "https://a/2": WebPushIndisponivelError("x"),
        }
    )
    canal, usuario_id, _, _ = _cenario("https://a/1", "https://a/2", "https://a/3", cliente=cliente)
    caplog.set_level(logging.INFO)

    canal.entregar(_notificacao(usuario_id))

    registro = next(r for r in caplog.records if getattr(r, "evento", None) == "push_web_enviado")
    assert registro.inscricoes == 3
    assert registro.entregues == 1
    assert registro.expiradas == 1
    assert registro.falhas == 1
    assert all("https://a/" not in str(vars(r)) for r in caplog.records)


def test_erro_inesperado_numa_inscricao_nao_impede_as_outras():
    cliente = _ClienteFalso({"https://a/1": ValueError("chave corrompida")})
    canal, usuario_id, _, _ = _cenario("https://a/1", "https://a/2", cliente=cliente)

    canal.entregar(_notificacao(usuario_id))

    assert [e for e, _ in cliente.enviados] == ["https://a/1", "https://a/2"]
