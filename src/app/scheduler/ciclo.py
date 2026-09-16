from __future__ import annotations

import logging
from collections.abc import Callable
from uuid import UUID

from app.domain.entities.ativo import Ativo
from app.domain.enums.periodo_historico import PeriodoHistorico
from app.domain.enums.tipo_ativo import TipoAtivo
from app.repositories.interfaces.alerta_repository import AlertaRepository
from app.repositories.interfaces.ativo_repository import AtivoRepository
from app.repositories.interfaces.sinal_repository import SinalRepository
from app.repositories.interfaces.watchlist_repository import WatchlistRepository
from app.services.alerta_service import AlertaService
from app.services.ativo_service import AtivoService
from app.services.dados_mercado_service import DadosMercadoService
from app.services.notificacao_service import NotificacaoService
from app.services.sinal_service import SinalService

logger = logging.getLogger(__name__)


def executar_ciclo_monitoramento(
    tipos_ativo: set[TipoAtivo],
    ativo_repository: AtivoRepository,
    watchlist_repository: WatchlistRepository,
    alerta_repository: AlertaRepository,
    sinal_repository: SinalRepository,
    dados_mercado_service: DadosMercadoService,
    ativo_service: AtivoService,
    alerta_service: AlertaService,
    sinal_service: SinalService,
    notificacao_service: NotificacaoService,
    ao_falhar_ativo: Callable[[], None] | None = None,
) -> None:
    ids_com_watchlist = set(watchlist_repository.listar_ativos_distintos_ativos())
    ids_com_alerta = set(alerta_repository.listar_ativos_distintos_com_alerta_ativo())

    for ativo_id in ids_com_watchlist | ids_com_alerta:
        ativo = ativo_repository.buscar_por_id(ativo_id)
        if ativo is None or ativo.tipo not in tipos_ativo:
            continue

        try:
            _processar_ativo(
                ativo_id=ativo_id,
                ativo=ativo,
                em_watchlist=ativo_id in ids_com_watchlist,
                watchlist_repository=watchlist_repository,
                sinal_repository=sinal_repository,
                dados_mercado_service=dados_mercado_service,
                ativo_service=ativo_service,
                alerta_service=alerta_service,
                sinal_service=sinal_service,
                notificacao_service=notificacao_service,
            )
        except Exception:
            logger.warning(
                "Falha ao processar ativo %s no ciclo de monitoramento.", ativo_id, exc_info=True
            )
            if ao_falhar_ativo is not None:
                ao_falhar_ativo()


def _processar_ativo(
    ativo_id: UUID,
    ativo: Ativo,
    em_watchlist: bool,
    watchlist_repository: WatchlistRepository,
    sinal_repository: SinalRepository,
    dados_mercado_service: DadosMercadoService,
    ativo_service: AtivoService,
    alerta_service: AlertaService,
    sinal_service: SinalService,
    notificacao_service: NotificacaoService,
) -> None:
    cotacao = dados_mercado_service.buscar_cotacao_atual(ativo.ticker)

    for alerta in alerta_service.avaliar_alertas(ativo_id, cotacao.preco):
        notificacao_service.enviar_alerta_personalizado(alerta.usuario_id, alerta, cotacao)

    if not em_watchlist:
        return

    vigentes_antes = {
        sinal.regra_id
        for sinal in sinal_repository.listar_por_ativo(ativo_id)
        if sinal.data_desativacao is None
    }

    ativo_service.historico(ativo_id, PeriodoHistorico.UM_MES)
    vigentes = sinal_service.avaliar_ativo(ativo_id)
    novos = [sinal for sinal in vigentes if sinal.regra_id not in vigentes_antes]
    if not novos:
        return

    watchlists = watchlist_repository.listar_por_ativo(ativo_id)
    for sinal in novos:
        for watchlist in watchlists:
            if watchlist.notificar:
                notificacao_service.enviar_alerta(watchlist.usuario_id, sinal, ativo)
