from __future__ import annotations

import logging

from app.domain.enums.periodo_historico import PeriodoHistorico
from app.domain.indices_referencia import IBOVESPA_NOME, IBOVESPA_TICKER
from app.integrations.brapi.client import BrapiIndisponivelError, TickerNaoEncontradoError
from app.services.ativo_service import AtivoService

logger = logging.getLogger(__name__)


def atualizar_indices_referencia(
    ativo_service: AtivoService, periodo_backfill: PeriodoHistorico, minimo_cotacoes: int
) -> None:
    ibovespa = ativo_service.buscar_ou_criar_indice(IBOVESPA_TICKER, IBOVESPA_NOME)
    try:
        ativo_service.atualizar_historico(ibovespa.id, periodo_backfill, minimo_cotacoes)
    except (BrapiIndisponivelError, TickerNaoEncontradoError):
        logger.warning("Falha ao atualizar o historico do Ibovespa.", exc_info=True)
