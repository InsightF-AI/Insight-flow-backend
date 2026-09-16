from datetime import UTC, datetime
from uuid import uuid4

from app.domain.entities.notificacao import Notificacao
from app.domain.enums.tipo_notificacao import TipoNotificacao


def test_cria_notificacao_nao_lida_por_padrao():
    notificacao = Notificacao(
        id=uuid4(),
        usuario_id=uuid4(),
        ativo_id=uuid4(),
        tipo=TipoNotificacao.ALERTA_DISPARADO,
        mensagem="PETR4 atingiu o alvo de 40.00 BRL (preco maior ou igual)",
        contexto={"valor_alvo": "40.00"},
        criado_em=datetime(2026, 9, 16, 12, 0, 0, tzinfo=UTC),
    )

    assert notificacao.lida is False
    assert notificacao.contexto == {"valor_alvo": "40.00"}
