from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.domain.entities.notificacao import Notificacao
from app.domain.enums.tipo_notificacao import TipoNotificacao
from app.notifications.payload_push import payload_push


def _notificacao(tipo, ativo_id=None) -> Notificacao:
    return Notificacao(
        id=uuid4(),
        usuario_id=uuid4(),
        ativo_id=ativo_id,
        tipo=tipo,
        mensagem="PETR4 atingiu o alvo",
        contexto={},
        criado_em=datetime(2026, 10, 7, tzinfo=UTC),
    )


@pytest.mark.parametrize(
    ("tipo", "titulo"),
    [
        (TipoNotificacao.SINAL_ATIVADO, "Sinal técnico"),
        (TipoNotificacao.ALERTA_DISPARADO, "Alerta de preço"),
        (TipoNotificacao.RESUMO_DIARIO, "Resumo diário"),
    ],
)
def test_titulo_por_tipo(tipo, titulo):
    assert payload_push(_notificacao(tipo))["title"] == titulo


def test_payload_completo():
    ativo_id = uuid4()
    notificacao = _notificacao(TipoNotificacao.ALERTA_DISPARADO, ativo_id)

    assert payload_push(notificacao) == {
        "title": "Alerta de preço",
        "body": "PETR4 atingiu o alvo",
        "data": {
            "notificacao_id": str(notificacao.id),
            "tipo": "ALERTA_DISPARADO",
            "ativo_id": str(ativo_id),
        },
    }


def test_sem_ativo_manda_ativo_id_nulo():
    assert payload_push(_notificacao(TipoNotificacao.RESUMO_DIARIO))["data"]["ativo_id"] is None
