from __future__ import annotations

from pydantic_core import to_jsonable_python

from app.domain.entities.notificacao import Notificacao


def notificacao_para_dict(notificacao: Notificacao) -> dict:
    return to_jsonable_python(
        {
            "id": notificacao.id,
            "ativo_id": notificacao.ativo_id,
            "tipo": notificacao.tipo,
            "mensagem": notificacao.mensagem,
            "contexto": notificacao.contexto,
            "lida": notificacao.lida,
            "criado_em": notificacao.criado_em,
        }
    )
