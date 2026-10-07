from datetime import UTC, datetime
from uuid import uuid4

from app.api.v1.schemas.notificacao import NotificacaoResponse
from app.domain.entities.notificacao import Notificacao
from app.domain.enums.tipo_notificacao import TipoNotificacao
from app.notifications.serializacao import notificacao_para_dict


def _notificacao(ativo_id) -> Notificacao:
    return Notificacao(
        id=uuid4(),
        usuario_id=uuid4(),
        ativo_id=ativo_id,
        tipo=TipoNotificacao.ALERTA_DISPARADO,
        mensagem="PETR4 atingiu o alvo",
        contexto={"alerta_id": "x", "preco": "40.00"},
        criado_em=datetime(2026, 10, 4, 12, 0, tzinfo=UTC),
    )


def test_serializacao_igual_ao_json_do_endpoint_rest():
    notificacao = _notificacao(uuid4())

    assert notificacao_para_dict(notificacao) == NotificacaoResponse.de(notificacao).model_dump(
        mode="json"
    )


def test_serializacao_sem_ativo_igual_ao_json_do_endpoint_rest():
    notificacao = _notificacao(None)

    assert notificacao_para_dict(notificacao) == NotificacaoResponse.de(notificacao).model_dump(
        mode="json"
    )
