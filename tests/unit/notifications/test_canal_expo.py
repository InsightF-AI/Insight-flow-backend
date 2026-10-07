import logging
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.domain.entities.dispositivo_push import DispositivoPush
from app.domain.entities.notificacao import Notificacao
from app.domain.enums.tipo_notificacao import TipoNotificacao
from app.integrations.expo.client import ExpoIndisponivelError, ResultadoEnvio
from app.notifications.canal_expo import CanalExpo
from tests.fixtures.fake_dispositivo_push_repository import FakeDispositivoPushRepository
from tests.fixtures.fake_ticket_push_repository import FakeTicketPushRepository

_AGORA = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)


class _ClienteFalso:
    def __init__(self, erros: dict[str, str] | None = None, falhar: bool = False):
        self.enviadas: list[dict] = []
        self._erros = erros or {}
        self._falhar = falhar

    def enviar(self, mensagens: list[dict]) -> list[ResultadoEnvio]:
        if self._falhar:
            raise ExpoIndisponivelError("fora do ar")
        self.enviadas.extend(mensagens)
        return [
            ResultadoEnvio(token=m["to"], ticket_id=None, erro=self._erros[m["to"]])
            if m["to"] in self._erros
            else ResultadoEnvio(token=m["to"], ticket_id=f"ticket-{m['to']}", erro=None)
            for m in mensagens
        ]


def _notificacao(usuario_id, tipo=TipoNotificacao.ALERTA_DISPARADO, ativo_id=None) -> Notificacao:
    return Notificacao(
        id=uuid4(),
        usuario_id=usuario_id,
        ativo_id=ativo_id,
        tipo=tipo,
        mensagem="PETR4 atingiu o alvo",
        contexto={},
        criado_em=_AGORA,
    )


def _cenario(*tokens: str, cliente: _ClienteFalso | None = None):
    usuario_id = uuid4()
    dispositivos = FakeDispositivoPushRepository()
    for token in tokens:
        dispositivos.salvar(
            DispositivoPush(
                id=uuid4(),
                usuario_id=usuario_id,
                token=token,
                ativo=True,
                criado_em=_AGORA,
                atualizado_em=_AGORA,
            )
        )
    tickets = FakeTicketPushRepository()
    cliente = cliente or _ClienteFalso()
    canal = CanalExpo(dispositivos, tickets, cliente, agora=lambda: _AGORA)
    return canal, usuario_id, dispositivos, tickets, cliente


def test_sem_dispositivos_nao_chama_a_expo():
    canal, usuario_id, _, tickets, cliente = _cenario()

    canal.entregar(_notificacao(usuario_id))

    assert cliente.enviadas == []
    assert tickets.listar_todos() == []


def test_envia_uma_mensagem_por_dispositivo_com_payload_completo():
    canal, usuario_id, _, _, cliente = _cenario("T1", "T2")
    ativo_id = uuid4()
    notificacao = _notificacao(usuario_id, ativo_id=ativo_id)

    canal.entregar(notificacao)

    assert [m["to"] for m in cliente.enviadas] == ["T1", "T2"]
    assert cliente.enviadas[0] == {
        "to": "T1",
        "title": "Alerta de preço",
        "body": "PETR4 atingiu o alvo",
        "data": {
            "notificacao_id": str(notificacao.id),
            "tipo": "ALERTA_DISPARADO",
            "ativo_id": str(ativo_id),
        },
        "sound": "default",
        "priority": "high",
    }


@pytest.mark.parametrize(
    ("tipo", "titulo"),
    [
        (TipoNotificacao.SINAL_ATIVADO, "Sinal técnico"),
        (TipoNotificacao.ALERTA_DISPARADO, "Alerta de preço"),
        (TipoNotificacao.RESUMO_DIARIO, "Resumo diário"),
    ],
)
def test_titulo_por_tipo(tipo, titulo):
    canal, usuario_id, _, _, cliente = _cenario("T1")

    canal.entregar(_notificacao(usuario_id, tipo=tipo))

    assert cliente.enviadas[0]["title"] == titulo


def test_resumo_diario_sem_ativo_manda_ativo_id_nulo():
    canal, usuario_id, _, _, cliente = _cenario("T1")

    canal.entregar(_notificacao(usuario_id, tipo=TipoNotificacao.RESUMO_DIARIO))

    assert cliente.enviadas[0]["data"]["ativo_id"] is None


def test_tickets_ok_sao_salvos_com_token_e_horario():
    canal, usuario_id, _, tickets, _ = _cenario("T1")

    canal.entregar(_notificacao(usuario_id))

    (ticket,) = tickets.listar_todos()
    assert ticket.id == "ticket-T1"
    assert ticket.token == "T1"
    assert ticket.criado_em == _AGORA


def test_device_not_registered_desativa_o_token_e_nao_salva_ticket():
    cliente = _ClienteFalso(erros={"T1": "DeviceNotRegistered"})
    canal, usuario_id, dispositivos, tickets, _ = _cenario("T1", "T2", cliente=cliente)

    canal.entregar(_notificacao(usuario_id))

    assert [d.token for d in dispositivos.listar_ativos_por_usuario(usuario_id)] == ["T2"]
    assert [t.id for t in tickets.listar_todos()] == ["ticket-T2"]


def test_outro_erro_mantem_o_token_e_loga_aviso(caplog):
    cliente = _ClienteFalso(erros={"T1": "MessageTooBig"})
    canal, usuario_id, dispositivos, _, _ = _cenario("T1", cliente=cliente)
    caplog.set_level(logging.INFO)

    canal.entregar(_notificacao(usuario_id))

    assert len(dispositivos.listar_ativos_por_usuario(usuario_id)) == 1
    aviso = next(r for r in caplog.records if getattr(r, "evento", None) == "push_recusado")
    assert aviso.levelno == logging.WARNING
    assert aviso.erro == "MessageTooBig"


def test_expo_fora_do_ar_propaga_o_erro():
    canal, usuario_id, _, _, _ = _cenario("T1", cliente=_ClienteFalso(falhar=True))

    with pytest.raises(ExpoIndisponivelError):
        canal.entregar(_notificacao(usuario_id))


def test_loga_push_enviado_sem_tokens(caplog):
    cliente = _ClienteFalso(erros={"T2": "DeviceNotRegistered"})
    canal, usuario_id, _, _, _ = _cenario("T1", "T2", cliente=cliente)
    caplog.set_level(logging.INFO)

    canal.entregar(_notificacao(usuario_id))

    registro = next(r for r in caplog.records if getattr(r, "evento", None) == "push_enviado")
    assert registro.dispositivos == 2
    assert registro.erros == 1
    assert "T1" not in str(vars(registro))
