from __future__ import annotations

import logging

from app.domain.indices_referencia import IBOVESPA_NOME, IBOVESPA_TICKER
from app.domain.value_objects.politica_historico import PoliticaHistorico
from app.integrations.erros import FonteDadosIndisponivelError, TickerNaoEncontradoError
from app.services.ativo_service import AtivoService

logger = logging.getLogger(__name__)


def atualizar_indices_referencia(ativo_service: AtivoService, politica: PoliticaHistorico) -> None:
    ibovespa = ativo_service.buscar_ou_criar_indice(IBOVESPA_TICKER, IBOVESPA_NOME)
    try:
        ativo_service.atualizar_historico(ibovespa.id, politica)
    except (FonteDadosIndisponivelError, TickerNaoEncontradoError):
        logger.warning("Falha ao atualizar o historico do Ibovespa.", exc_info=True)
