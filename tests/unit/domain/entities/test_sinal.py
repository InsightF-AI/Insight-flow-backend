from datetime import UTC, datetime
from uuid import uuid4

from app.domain.entities.sinal import Sinal


def test_cria_sinal_ativo_sem_data_de_desativacao():
    sinal = Sinal(
        id=uuid4(),
        ativo_id=uuid4(),
        regra_id=uuid4(),
        data_ativacao=datetime(2026, 9, 8, 18, 0, 0, tzinfo=UTC),
        contexto={"rsi": 28.4},
    )

    assert sinal.data_desativacao is None
    assert sinal.contexto == {"rsi": 28.4}
