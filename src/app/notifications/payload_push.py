from __future__ import annotations

from app.domain.entities.notificacao import Notificacao
from app.domain.enums.tipo_notificacao import TipoNotificacao

_TITULOS = {
    TipoNotificacao.SINAL_ATIVADO: "Sinal técnico",
    TipoNotificacao.ALERTA_DISPARADO: "Alerta de preço",
    TipoNotificacao.RESUMO_DIARIO: "Resumo diário",
}


def payload_push(notificacao: Notificacao) -> dict:
    return {
        "title": _TITULOS.get(notificacao.tipo, "InsightFlow"),
        "body": notificacao.mensagem,
        "data": {
            "notificacao_id": str(notificacao.id),
            "tipo": notificacao.tipo.value,
            "ativo_id": str(notificacao.ativo_id) if notificacao.ativo_id else None,
        },
    }
