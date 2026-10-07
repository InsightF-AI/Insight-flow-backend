from datetime import UTC, datetime, timedelta

import pytest

from app.domain.entities.ticket_push import TicketPush
from app.repositories.sqlalchemy.ticket_push_repository import SqlAlchemyTicketPushRepository

pytestmark = pytest.mark.integration

_AGORA = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)


def _ticket(id_: str, minutos_atras: int) -> TicketPush:
    return TicketPush(
        id=id_, token="ExponentPushToken[t]", criado_em=_AGORA - timedelta(minutes=minutos_atras)
    )


def test_listar_anteriores_a_filtra_pelo_limite_e_ordena_do_mais_antigo(session):
    repositorio = SqlAlchemyTicketPushRepository(session)
    repositorio.salvar_muitos([_ticket("novo", 5), _ticket("velho", 60), _ticket("medio", 20)])

    encontrados = repositorio.listar_anteriores_a(_AGORA - timedelta(minutes=15), 10)

    assert [t.id for t in encontrados] == ["velho", "medio"]


def test_listar_anteriores_a_respeita_a_quantidade(session):
    repositorio = SqlAlchemyTicketPushRepository(session)
    repositorio.salvar_muitos([_ticket(f"t{i}", 30 + i) for i in range(5)])

    assert len(repositorio.listar_anteriores_a(_AGORA, 2)) == 2


def test_remover_muitos(session):
    repositorio = SqlAlchemyTicketPushRepository(session)
    repositorio.salvar_muitos([_ticket("a", 30), _ticket("b", 30), _ticket("c", 30)])

    repositorio.remover_muitos(["a", "c"])

    assert [t.id for t in repositorio.listar_anteriores_a(_AGORA, 10)] == ["b"]


def test_salvar_muitos_com_lista_vazia_nao_lanca_erro(session):
    SqlAlchemyTicketPushRepository(session).salvar_muitos([])
