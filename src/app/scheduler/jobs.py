from __future__ import annotations

from functools import lru_cache

import httpx
import redis
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.db.session import criar_session_factory
from app.domain.enums.tipo_ativo import TipoAtivo
from app.integrations.bcb.client import BcbClient
from app.integrations.brapi.client import BrapiClient
from app.repositories.sqlalchemy.alerta_repository import SqlAlchemyAlertaRepository
from app.repositories.sqlalchemy.ativo_repository import SqlAlchemyAtivoRepository
from app.repositories.sqlalchemy.cotacao_repository import SqlAlchemyCotacaoRepository
from app.repositories.sqlalchemy.indicador_tecnico_repository import (
    SqlAlchemyIndicadorTecnicoRepository,
)
from app.repositories.sqlalchemy.notificacao_repository import SqlAlchemyNotificacaoRepository
from app.repositories.sqlalchemy.sinal_repository import SqlAlchemySinalRepository
from app.repositories.sqlalchemy.watchlist_repository import SqlAlchemyWatchlistRepository
from app.scheduler.ciclo import executar_ciclo_monitoramento
from app.services.alerta_service import AlertaService
from app.services.ativo_service import AtivoService
from app.services.cached_cambio_service import CachedCambioService
from app.services.cached_dados_mercado_service import CachedDadosMercadoService
from app.services.cambio_service import BcbCambioService
from app.services.dados_mercado_service import DadosMercadoService
from app.services.indicador_service import IndicadorService
from app.services.notificacao_service import NotificacaoService
from app.services.redis_mercado_cache import RedisMercadoCache
from app.services.sinal_service import SinalService

_RENDA_VARIAVEL = {TipoAtivo.ACAO, TipoAtivo.FII, TipoAtivo.ETF, TipoAtivo.BDR}
_CRIPTO = {TipoAtivo.CRIPTO}


def registrar_jobs(scheduler: BackgroundScheduler, settings: Settings) -> None:
    scheduler.add_job(
        lambda: _executar_ciclo(settings, _RENDA_VARIAVEL),
        "interval",
        minutes=settings.scheduler_intervalo_renda_variavel_minutos,
        id="ciclo_renda_variavel",
    )
    scheduler.add_job(
        lambda: _executar_ciclo(settings, _CRIPTO),
        "interval",
        minutes=settings.scheduler_intervalo_cripto_minutos,
        id="ciclo_cripto",
    )


@lru_cache
def _session_factory(database_url: str) -> sessionmaker:
    return criar_session_factory(database_url)


@lru_cache
def _brapi_http_client(base_url: str) -> httpx.Client:
    return httpx.Client(base_url=base_url, timeout=10.0)


@lru_cache
def _bcb_http_client(base_url: str) -> httpx.Client:
    return httpx.Client(base_url=base_url, timeout=10.0)


@lru_cache
def _redis_client(redis_url: str) -> redis.Redis:
    return redis.Redis.from_url(redis_url)


def _executar_ciclo(settings: Settings, tipos_ativo: set[TipoAtivo]) -> None:
    session = _session_factory(settings.database_url)()
    try:
        cache = RedisMercadoCache(_redis_client(settings.redis_url))
        brapi_client = BrapiClient(
            _brapi_http_client(settings.brapi_base_url),
            settings.brapi_api_key or None,
        )
        bcb_client = BcbClient(_bcb_http_client(settings.bcb_base_url))

        ativo_repository = SqlAlchemyAtivoRepository(session)
        watchlist_repository = SqlAlchemyWatchlistRepository(session)
        alerta_repository = SqlAlchemyAlertaRepository(session)
        sinal_repository = SqlAlchemySinalRepository(session)
        cotacao_repository = SqlAlchemyCotacaoRepository(session)
        indicador_repository = SqlAlchemyIndicadorTecnicoRepository(session)
        notificacao_repository = SqlAlchemyNotificacaoRepository(session)

        dados_mercado_service = CachedDadosMercadoService(
            DadosMercadoService(brapi_client),
            cache,
            ttl_cotacao_atual=settings.cache_ttl_cotacao_atual_segundos,
        )
        cambio_service = CachedCambioService(
            BcbCambioService(bcb_client),
            cache,
            ttl_segundos=settings.cache_ttl_cambio_segundos,
            ttl_fallback_segundos=settings.cache_ttl_cambio_fallback_segundos,
        )
        indicador_service = IndicadorService(
            ativo_repository, cotacao_repository, indicador_repository
        )

        executar_ciclo_monitoramento(
            tipos_ativo,
            ativo_repository,
            watchlist_repository,
            alerta_repository,
            sinal_repository,
            dados_mercado_service,
            AtivoService(ativo_repository, dados_mercado_service, cotacao_repository),
            AlertaService(
                alerta_repository, ativo_repository, dados_mercado_service, cambio_service
            ),
            SinalService(ativo_repository, cotacao_repository, indicador_service, sinal_repository),
            NotificacaoService(notificacao_repository),
            ao_falhar_ativo=session.rollback,
        )
    finally:
        session.close()
