from datetime import UTC, datetime
from uuid import uuid4

from app.domain.entities.watchlist import Watchlist


def test_adicionar_habilita_notificacao_por_padrao():
    watchlist = Watchlist.adicionar(
        id=uuid4(),
        usuario_id=uuid4(),
        ativo_id=uuid4(),
        adicionado_em=datetime(2026, 9, 8, 18, 0, 0, tzinfo=UTC),
    )

    assert watchlist.notificar is True


def test_desabilitar_notificacao_marca_notificar_como_falso():
    watchlist = Watchlist.adicionar(
        id=uuid4(),
        usuario_id=uuid4(),
        ativo_id=uuid4(),
        adicionado_em=datetime(2026, 9, 8, 18, 0, 0, tzinfo=UTC),
    )

    watchlist.desabilitar_notificacao()

    assert watchlist.notificar is False


def test_habilitar_notificacao_marca_notificar_como_verdadeiro():
    watchlist = Watchlist.adicionar(
        id=uuid4(),
        usuario_id=uuid4(),
        ativo_id=uuid4(),
        adicionado_em=datetime(2026, 9, 8, 18, 0, 0, tzinfo=UTC),
    )
    watchlist.desabilitar_notificacao()

    watchlist.habilitar_notificacao()

    assert watchlist.notificar is True
