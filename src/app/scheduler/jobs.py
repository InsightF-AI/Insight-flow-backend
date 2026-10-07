from __future__ import annotations

from functools import lru_cache

import httpx
import redis
import redis.asyncio
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import sessionmaker

from app.ai.providers.fabrica import criar_provedor_llm
from app.core.config import Settings
from app.db.session import criar_session_factory
from app.domain.enums.tipo_ativo import TipoAtivo
from app.integrations.bcb.client import BcbClient
from app.integrations.binance.client import BinanceClient
from app.integrations.brapi.client import BrapiClient
from app.integrations.limitadores import limitador_compartilhado
from app.notifications.canal import CanalTempoReal
from app.notifications.redis_barramento import RedisBarramentoNotificacoes
from app.repositories.interfaces.notificacao_repository import NotificacaoRepository
from app.repositories.sqlalchemy.alerta_repository import SqlAlchemyAlertaRepository
from app.repositories.sqlalchemy.ativo_repository import SqlAlchemyAtivoRepository
from app.repositories.sqlalchemy.cotacao_repository import SqlAlchemyCotacaoRepository
from app.repositories.sqlalchemy.indicador_tecnico_repository import (
    SqlAlchemyIndicadorTecnicoRepository,
)
from app.repositories.sqlalchemy.notificacao_repository import SqlAlchemyNotificacaoRepository
from app.repositories.sqlalchemy.operacao_repository import SqlAlchemyOperacaoRepository
from app.repositories.sqlalchemy.sinal_repository import SqlAlchemySinalRepository
from app.repositories.sqlalchemy.watchlist_repository import SqlAlchemyWatchlistRepository
from app.scheduler.ciclo import executar_ciclo_monitoramento
from app.scheduler.execucao import executar_job
from app.scheduler.indices_referencia import atualizar_indices_referencia
from app.scheduler.resumo_diario import gerar_resumos_diarios
from app.services.alerta_service import AlertaService
from app.services.ativo_service import AtivoService
from app.services.cached_cambio_service import CachedCambioService
from app.services.cached_dados_mercado_service import CachedDadosMercadoService
from app.services.cambio_service import BcbCambioService
from app.services.dados_mercado_service import DadosMercadoService
from app.services.indicador_service import IndicadorService
from app.services.mercado_cache import MercadoCache
from app.services.notificacao_service import NotificacaoService
from app.services.portfolio_service import PortfolioService
from app.services.redis_mercado_cache import RedisMercadoCache
from app.services.resumo_carteira_service import ResumoCarteiraService
from app.services.roteador_dados_mercado_service import RoteadorDadosMercadoService
from app.services.sinal_service import SinalService

_RENDA_VARIAVEL = {TipoAtivo.ACAO, TipoAtivo.FII, TipoAtivo.ETF, TipoAtivo.BDR}
_CRIPTO = {TipoAtivo.CRIPTO}


def registrar_jobs(scheduler: BackgroundScheduler, settings: Settings) -> None:
    scheduler.add_job(
        lambda: executar_job(
            "ciclo_renda_variavel", lambda: _executar_ciclo(settings, _RENDA_VARIAVEL)
        ),
        "interval",
        minutes=settings.scheduler_intervalo_renda_variavel_minutos,
        id="ciclo_renda_variavel",
    )
    scheduler.add_job(
        lambda: executar_job("ciclo_cripto", lambda: _executar_ciclo(settings, _CRIPTO)),
        "interval",
        minutes=settings.scheduler_intervalo_cripto_minutos,
        id="ciclo_cripto",
    )
    scheduler.add_job(
        lambda: executar_job("indices_referencia", lambda: _executar_indices_referencia(settings)),
        "cron",
        hour=settings.indices_referencia_hora,
        minute=settings.indices_referencia_minuto,
        timezone="America/Sao_Paulo",
        id="indices_referencia",
    )
    if settings.ai_habilitada and settings.gemini_api_key and settings.ai_provider == "gemini":
        scheduler.add_job(
            lambda: executar_job("resumo_diario", lambda: _executar_resumos_diarios(settings)),
            "cron",
            hour=settings.resumo_diario_hora,
            minute=settings.resumo_diario_minuto,
            timezone="America/Sao_Paulo",
            id="resumo_diario",
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
def _binance_http_client(base_url: str) -> httpx.Client:
    return httpx.Client(base_url=base_url, timeout=10.0)


@lru_cache
def _redis_client(redis_url: str) -> redis.Redis:
    return redis.Redis.from_url(redis_url)


@lru_cache
def _redis_async_client(redis_url: str) -> redis.asyncio.Redis:
    return redis.asyncio.Redis.from_url(redis_url)


def _notificacao_service(
    settings: Settings, notificacao_repository: NotificacaoRepository
) -> NotificacaoService:
    barramento = RedisBarramentoNotificacoes(
        _redis_client(settings.redis_url), _redis_async_client(settings.redis_url)
    )
    return NotificacaoService(notificacao_repository, canais=[CanalTempoReal(barramento)])


def _dados_mercado_service(settings: Settings, cache: MercadoCache) -> DadosMercadoService:
    brapi_client = BrapiClient(
        _brapi_http_client(settings.brapi_base_url),
        settings.brapi_api_key or None,
        limitador=limitador_compartilhado(
            "brapi",
            settings.brapi_requisicoes_por_minuto,
            settings.integracoes_espera_maxima_segundos,
        ),
        politica=settings.politica_retentativa(),
    )
    return CachedDadosMercadoService(
        RoteadorDadosMercadoService(
            DadosMercadoService(brapi_client),
            BinanceClient(
                _binance_http_client(settings.binance_base_url),
                limitador=limitador_compartilhado(
                    "binance",
                    settings.binance_requisicoes_por_minuto,
                    settings.integracoes_espera_maxima_segundos,
                ),
                politica=settings.politica_retentativa(),
            ),
            cache,
            ttl_catalogo_segundos=settings.cache_ttl_catalogo_cripto_segundos,
        ),
        cache,
        ttl_cotacao_atual=settings.cache_ttl_cotacao_atual_segundos,
        ttl_historico=settings.cache_ttl_historico_segundos,
    )


def _executar_ciclo(settings: Settings, tipos_ativo: set[TipoAtivo]) -> None:
    session = _session_factory(settings.database_url)()
    try:
        cache = RedisMercadoCache(_redis_client(settings.redis_url))
        bcb_client = BcbClient(_bcb_http_client(settings.bcb_base_url))

        ativo_repository = SqlAlchemyAtivoRepository(session)
        watchlist_repository = SqlAlchemyWatchlistRepository(session)
        alerta_repository = SqlAlchemyAlertaRepository(session)
        sinal_repository = SqlAlchemySinalRepository(session)
        cotacao_repository = SqlAlchemyCotacaoRepository(session)
        indicador_repository = SqlAlchemyIndicadorTecnicoRepository(session)
        notificacao_repository = SqlAlchemyNotificacaoRepository(session)

        dados_mercado_service = _dados_mercado_service(settings, cache)
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
            _notificacao_service(settings, notificacao_repository),
            politica=settings.politica_historico(),
            ao_falhar_ativo=session.rollback,
        )
    finally:
        session.close()


def _executar_indices_referencia(settings: Settings) -> None:
    session = _session_factory(settings.database_url)()
    try:
        dados_mercado_service = _dados_mercado_service(
            settings, RedisMercadoCache(_redis_client(settings.redis_url))
        )
        atualizar_indices_referencia(
            AtivoService(
                SqlAlchemyAtivoRepository(session),
                dados_mercado_service,
                SqlAlchemyCotacaoRepository(session),
            ),
            settings.politica_historico(),
        )
    finally:
        session.close()


def _executar_resumos_diarios(settings: Settings) -> None:
    session = _session_factory(settings.database_url)()
    try:
        cache = RedisMercadoCache(_redis_client(settings.redis_url))
        bcb_client = BcbClient(_bcb_http_client(settings.bcb_base_url))

        operacao_repository = SqlAlchemyOperacaoRepository(session)
        ativo_repository = SqlAlchemyAtivoRepository(session)
        notificacao_repository = SqlAlchemyNotificacaoRepository(session)

        dados_mercado_service = _dados_mercado_service(settings, cache)
        cambio_service = CachedCambioService(
            BcbCambioService(bcb_client),
            cache,
            ttl_segundos=settings.cache_ttl_cambio_segundos,
            ttl_fallback_segundos=settings.cache_ttl_cambio_fallback_segundos,
        )
        portfolio_service = PortfolioService(
            operacao_repository,
            ativo_repository,
            dados_mercado_service,
            cambio_service,
            bcb_client,
            SqlAlchemyCotacaoRepository(session),
        )
        resumo_service = ResumoCarteiraService(
            _notificacao_service(settings, notificacao_repository),
            portfolio_service,
            criar_provedor_llm(settings),
        )

        gerar_resumos_diarios(
            operacao_repository,
            resumo_service,
            settings.gemini_intervalo_entre_chamadas_segundos,
            ao_falhar_usuario=session.rollback,
        )
    finally:
        session.close()
