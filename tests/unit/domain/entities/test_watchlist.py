from datetime import datetime
from uuid import uuid4

from app.domain.entities.watchlist import Watchlist


def test_adicionar_habilita_notificacao_por_padrao():
    watchlist = Watchlist.adicionar(
        id=uuid4(),
        usuario_id=uuid4(),
        ativo_id=uuid4(),
        adicionado_em=datetime(2026, 9, 8, 18, 0, 0),
    )

    assert watchlist.notificar is True
