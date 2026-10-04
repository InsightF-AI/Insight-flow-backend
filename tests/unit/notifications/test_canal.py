from datetime import UTC, datetime
from uuid import uuid4

from app.domain.entities.notificacao import Notificacao
from app.domain.enums.tipo_notificacao import TipoNotificacao
from app.notifications.canal import CanalTempoReal
from app.notifications.serializacao import notificacao_para_dict
from tests.fixtures.fake_barramento_notificacoes import FakeBarramentoNotificacoes


def test_canal_tempo_real_publica_no_canal_do_dono():
    barramento = FakeBarramentoNotificacoes()
    notificacao = Notificacao(
        id=uuid4(),
        usuario_id=uuid4(),
        ativo_id=None,
        tipo=TipoNotificacao.RESUMO_DIARIO,
        mensagem="Resumo diario da carteira",
        contexto={"texto": "ok"},
        criado_em=datetime(2026, 10, 4, 12, 0, tzinfo=UTC),
    )

    CanalTempoReal(barramento).entregar(notificacao)

    assert barramento.publicados == [
        (
            notificacao.usuario_id,
            {"tipo": "notificacao", "notificacao": notificacao_para_dict(notificacao)},
        )
    ]
