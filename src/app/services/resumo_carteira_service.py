from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from app.ai.contexto import calcular_hash, serializar
from app.ai.guardrails.aplicar import gerar_com_guardrail
from app.ai.prompts.resumo_diario import PROMPT_VERSAO_RESUMO, montar_prompt_resumo
from app.ai.providers.base import ProvedorLLM
from app.domain.entities.notificacao import Notificacao
from app.domain.enums.tipo_benchmark import TipoBenchmark
from app.services.notificacao_service import NotificacaoService
from app.services.portfolio_service import PortfolioService

_FUSO = ZoneInfo("America/Sao_Paulo")


class ResumoCarteiraService:
    def __init__(
        self,
        notificacao_service: NotificacaoService,
        portfolio_service: PortfolioService,
        provedor: ProvedorLLM,
        agora: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self._notificacao_service = notificacao_service
        self._portfolio_service = portfolio_service
        self._provedor = provedor
        self._agora = agora

    def gerar(self, usuario_id: UUID) -> Notificacao | None:
        if self._ja_gerado_hoje(usuario_id):
            return None
        if not self._portfolio_service.posicoes(usuario_id):
            return None

        contexto = self._montar_contexto(usuario_id)
        system, prompt = montar_prompt_resumo(contexto)
        texto = gerar_com_guardrail(lambda s: self._provedor.gerar_texto(s, prompt), system)
        return self._notificacao_service.enviar_resumo_diario(
            usuario_id,
            texto,
            {
                "modelo": self._provedor.modelo,
                "prompt_versao": PROMPT_VERSAO_RESUMO,
                "contexto_hash": calcular_hash(contexto),
            },
        )

    def _ja_gerado_hoje(self, usuario_id: UUID) -> bool:
        ultimo = self._notificacao_service.buscar_ultimo_resumo_diario(usuario_id)
        if ultimo is None:
            return False
        return ultimo.criado_em.astimezone(_FUSO).date() == self._agora().astimezone(_FUSO).date()

    def _montar_contexto(self, usuario_id: UUID) -> dict:
        return {
            "posicoes": serializar(self._portfolio_service.posicoes(usuario_id)),
            "rentabilidade": serializar(self._portfolio_service.rentabilidade(usuario_id)),
            "distribuicao": serializar(self._portfolio_service.distribuicao(usuario_id)),
            "benchmark_cdi": serializar(
                self._portfolio_service.comparativo_benchmark(usuario_id, TipoBenchmark.CDI)
            ),
        }
