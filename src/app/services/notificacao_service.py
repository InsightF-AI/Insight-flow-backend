from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domain.entities.alerta_personalizado import AlertaPersonalizado
from app.domain.entities.ativo import Ativo
from app.domain.entities.notificacao import Notificacao
from app.domain.entities.sinal import Sinal
from app.domain.enums.tipo_condicao_alerta import TipoCondicaoAlerta
from app.domain.enums.tipo_notificacao import TipoNotificacao
from app.domain.regras_sinal_padrao import buscar_regra_por_id
from app.integrations.brapi.client import CotacaoAtual
from app.repositories.interfaces.notificacao_repository import NotificacaoRepository
from app.services.exceptions import NotificacaoNaoEncontradaError

_CONDICAO_TEXTO = {
    TipoCondicaoAlerta.PRECO_MAIOR_IGUAL: "preco maior ou igual",
    TipoCondicaoAlerta.PRECO_MENOR_IGUAL: "preco menor ou igual",
}


class NotificacaoService:
    def __init__(self, notificacao_repository: NotificacaoRepository):
        self._notificacao_repository = notificacao_repository

    def enviar_alerta(self, usuario_id: UUID, sinal: Sinal, ativo: Ativo) -> Notificacao:
        regra = buscar_regra_por_id(sinal.regra_id)
        nome_regra = regra.nome if regra is not None else "sinal tecnico"
        notificacao = Notificacao(
            id=uuid4(),
            usuario_id=usuario_id,
            ativo_id=ativo.id,
            tipo=TipoNotificacao.SINAL_ATIVADO,
            mensagem=f"{ativo.ticker}: {nome_regra} detectado",
            contexto={"sinal_id": str(sinal.id), "regra_id": str(sinal.regra_id)},
            criado_em=datetime.now(UTC),
        )
        self._notificacao_repository.salvar(notificacao)
        return notificacao

    def enviar_alerta_personalizado(
        self, usuario_id: UUID, alerta: AlertaPersonalizado, cotacao: CotacaoAtual
    ) -> Notificacao:
        condicao_texto = _CONDICAO_TEXTO.get(alerta.tipo_condicao, "condicao atingida")
        mensagem = (
            f"{cotacao.ticker} atingiu o alvo de {alerta.valor_alvo} {alerta.moeda_alvo} "
            f"({condicao_texto})"
        )
        notificacao = Notificacao(
            id=uuid4(),
            usuario_id=usuario_id,
            ativo_id=alerta.ativo_id,
            tipo=TipoNotificacao.ALERTA_DISPARADO,
            mensagem=mensagem,
            contexto={"alerta_id": str(alerta.id), "preco": str(cotacao.preco)},
            criado_em=datetime.now(UTC),
        )
        self._notificacao_repository.salvar(notificacao)
        return notificacao

    def listar_notificacoes(
        self, usuario_id: UUID, apenas_nao_lidas: bool = False
    ) -> list[Notificacao]:
        return self._notificacao_repository.listar_por_usuario(usuario_id, apenas_nao_lidas)

    def marcar_como_lida(self, usuario_id: UUID, notificacao_id: UUID) -> Notificacao:
        notificacao = self._notificacao_repository.buscar_por_id(notificacao_id)
        if notificacao is None or notificacao.usuario_id != usuario_id:
            raise NotificacaoNaoEncontradaError(notificacao_id)

        notificacao.lida = True
        self._notificacao_repository.salvar(notificacao)
        return notificacao
