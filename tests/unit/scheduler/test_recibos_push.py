import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.domain.entities.dispositivo_push import DispositivoPush
from app.domain.entities.ticket_push import TicketPush
from app.integrations.expo.client import ReciboPush
from app.scheduler.recibos_push import conferir_recibos_push
from tests.fixtures.fake_dispositivo_push_repository import FakeDispositivoPushRepository
from tests.fixtures.fake_ticket_push_repository import FakeTicketPushRepository

_AGORA = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)


class _ClienteFalso:
    def __init__(self, recibos: dict[str, ReciboPush]):
        self._recibos = recibos
        self.consultas: list[list[str]] = []

    def buscar_recibos(self, ids: list[str]) -> dict[str, ReciboPush]:
        self.consultas.append(list(ids))
        return {i: self._recibos[i] for i in ids if i in self._recibos}


def _cenario(tickets: list[TicketPush], recibos: dict[str, ReciboPush]):
    ticket_repository = FakeTicketPushRepository()
    ticket_repository.salvar_muitos(tickets)
    dispositivo_repository = FakeDispositivoPushRepository()
    for token in {t.token for t in tickets}:
        dispositivo_repository.salvar(
            DispositivoPush(
                id=uuid4(),
                usuario_id=uuid4(),
                token=token,
                ativo=True,
                criado_em=_AGORA,
                atualizado_em=_AGORA,
            )
        )
    return ticket_repository, dispositivo_repository, _ClienteFalso(recibos)


def _ticket(id_: str, minutos: int, token: str = "T1") -> TicketPush:
    return TicketPush(id=id_, token=token, criado_em=_AGORA - timedelta(minutes=minutos))


def _executar(ticket_repository, dispositivo_repository, cliente, lote: int = 1000) -> None:
    conferir_recibos_push(ticket_repository, dispositivo_repository, cliente, _AGORA, lote=lote)


def test_ticket_com_menos_de_15_minutos_nao_e_consultado():
    tickets, dispositivos, cliente = _cenario([_ticket("a", 10)], {})

    _executar(tickets, dispositivos, cliente)

    assert cliente.consultas == []
    assert len(tickets.listar_todos()) == 1


def test_recibo_ok_remove_o_ticket():
    tickets, dispositivos, cliente = _cenario(
        [_ticket("a", 20)], {"a": ReciboPush(status="ok", erro=None)}
    )

    _executar(tickets, dispositivos, cliente)

    assert tickets.listar_todos() == []
    assert dispositivos.buscar_por_token("T1").ativo is True


def test_device_not_registered_desativa_o_token_e_remove_o_ticket():
    tickets, dispositivos, cliente = _cenario(
        [_ticket("a", 20)], {"a": ReciboPush(status="error", erro="DeviceNotRegistered")}
    )

    _executar(tickets, dispositivos, cliente)

    assert tickets.listar_todos() == []
    assert dispositivos.buscar_por_token("T1").ativo is False


def test_invalid_credentials_loga_erro_e_remove_o_ticket(caplog):
    tickets, dispositivos, cliente = _cenario(
        [_ticket("a", 20)], {"a": ReciboPush(status="error", erro="InvalidCredentials")}
    )
    caplog.set_level(logging.INFO)

    _executar(tickets, dispositivos, cliente)

    assert tickets.listar_todos() == []
    assert dispositivos.buscar_por_token("T1").ativo is True
    assert any(
        r.levelno == logging.ERROR and getattr(r, "erro", None) == "InvalidCredentials"
        for r in caplog.records
    )


def test_outro_erro_loga_aviso_e_remove_o_ticket(caplog):
    tickets, dispositivos, cliente = _cenario(
        [_ticket("a", 20)], {"a": ReciboPush(status="error", erro="MessageTooBig")}
    )
    caplog.set_level(logging.INFO)

    _executar(tickets, dispositivos, cliente)

    assert tickets.listar_todos() == []
    assert any(
        r.levelno == logging.WARNING and getattr(r, "erro", None) == "MessageTooBig"
        for r in caplog.records
    )


def test_recibo_ausente_com_menos_de_24h_mantem_o_ticket():
    tickets, dispositivos, cliente = _cenario([_ticket("a", 60)], {})

    _executar(tickets, dispositivos, cliente)

    assert [t.id for t in tickets.listar_todos()] == ["a"]


def test_recibo_ausente_com_24h_ou_mais_remove_o_ticket():
    tickets, dispositivos, cliente = _cenario([_ticket("a", 24 * 60)], {})

    _executar(tickets, dispositivos, cliente)

    assert tickets.listar_todos() == []


def test_processa_em_varios_lotes():
    lista = [_ticket(f"t{i}", 30 + i) for i in range(5)]
    tickets, dispositivos, cliente = _cenario(
        lista, {t.id: ReciboPush(status="ok", erro=None) for t in lista}
    )

    _executar(tickets, dispositivos, cliente, lote=2)

    assert [len(c) for c in cliente.consultas] == [2, 2, 1]
    assert tickets.listar_todos() == []


def test_lote_so_com_pendentes_encerra_sem_laco_infinito():
    lista = [_ticket(f"p{i}", 30) for i in range(3)]
    tickets, dispositivos, cliente = _cenario(lista, {})

    _executar(tickets, dispositivos, cliente, lote=2)

    assert len(cliente.consultas) == 1
    assert len(tickets.listar_todos()) == 3


def test_loga_resumo_da_conferencia(caplog):
    tickets, dispositivos, cliente = _cenario(
        [_ticket("a", 20), _ticket("b", 20, token="T2"), _ticket("c", 20)],
        {
            "a": ReciboPush(status="ok", erro=None),
            "b": ReciboPush(status="error", erro="DeviceNotRegistered"),
        },
    )
    caplog.set_level(logging.INFO)

    _executar(tickets, dispositivos, cliente)

    resumo = next(
        r for r in caplog.records if getattr(r, "evento", None) == "recibos_push_conferidos"
    )
    assert resumo.verificados == 2
    assert resumo.tokens_desativados == 1
    assert resumo.pendentes == 1
