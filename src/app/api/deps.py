from collections.abc import Generator
from functools import lru_cache

import httpx
import redis
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.core.security import TokenInvalidoError, decodificar_token
from app.db.session import criar_session_factory
from app.domain.entities.usuario import Usuario
from app.integrations.bcb.client import BcbClient
from app.integrations.brapi.client import BrapiClient
from app.repositories.interfaces.alerta_repository import AlertaRepository
from app.repositories.interfaces.ativo_repository import AtivoRepository
from app.repositories.interfaces.cotacao_repository import CotacaoRepository
from app.repositories.interfaces.indicador_tecnico_repository import IndicadorTecnicoRepository
from app.repositories.interfaces.notificacao_repository import NotificacaoRepository
from app.repositories.interfaces.operacao_repository import OperacaoRepository
from app.repositories.interfaces.sinal_repository import SinalRepository
from app.repositories.interfaces.usuario_repository import UsuarioRepository
from app.repositories.interfaces.watchlist_repository import WatchlistRepository
from app.repositories.sqlalchemy.alerta_repository import SqlAlchemyAlertaRepository
from app.repositories.sqlalchemy.ativo_repository import SqlAlchemyAtivoRepository
from app.repositories.sqlalchemy.cotacao_repository import SqlAlchemyCotacaoRepository
from app.repositories.sqlalchemy.indicador_tecnico_repository import (
    SqlAlchemyIndicadorTecnicoRepository,
)
from app.repositories.sqlalchemy.notificacao_repository import SqlAlchemyNotificacaoRepository
from app.repositories.sqlalchemy.operacao_repository import SqlAlchemyOperacaoRepository
from app.repositories.sqlalchemy.sinal_repository import SqlAlchemySinalRepository
from app.repositories.sqlalchemy.usuario_repository import SqlAlchemyUsuarioRepository
from app.repositories.sqlalchemy.watchlist_repository import SqlAlchemyWatchlistRepository
from app.services.alerta_service import AlertaService
from app.services.ativo_service import AtivoService
from app.services.cached_cambio_service import CachedCambioService
from app.services.cached_dados_mercado_service import CachedDadosMercadoService
from app.services.cambio_service import BcbCambioService, CambioService
from app.services.dados_mercado_service import DadosMercadoService
from app.services.indicador_service import IndicadorService
from app.services.mercado_cache import MercadoCache
from app.services.notificacao_service import NotificacaoService
from app.services.portfolio_service import PortfolioService
from app.services.redis_mercado_cache import RedisMercadoCache
from app.services.sinal_service import SinalService
from app.services.usuario_service import UsuarioService
from app.services.watchlist_service import WatchlistService

_bearer_scheme = HTTPBearer()


@lru_cache
def _session_factory(database_url: str) -> sessionmaker:
    return criar_session_factory(database_url)


def get_db_session(settings: Settings = Depends(get_settings)) -> Generator[Session, None, None]:
    session = _session_factory(settings.database_url)()
    try:
        yield session
    finally:
        session.close()


def get_usuario_repository(
    session: Session = Depends(get_db_session),
) -> UsuarioRepository:
    return SqlAlchemyUsuarioRepository(session)


def get_usuario_service(
    repository: UsuarioRepository = Depends(get_usuario_repository),
) -> UsuarioService:
    return UsuarioService(repository)


def get_ativo_repository(
    session: Session = Depends(get_db_session),
) -> AtivoRepository:
    return SqlAlchemyAtivoRepository(session)


def get_watchlist_repository(
    session: Session = Depends(get_db_session),
) -> WatchlistRepository:
    return SqlAlchemyWatchlistRepository(session)


def get_cotacao_repository(
    session: Session = Depends(get_db_session),
) -> CotacaoRepository:
    return SqlAlchemyCotacaoRepository(session)


def get_indicador_tecnico_repository(
    session: Session = Depends(get_db_session),
) -> IndicadorTecnicoRepository:
    return SqlAlchemyIndicadorTecnicoRepository(session)


def get_sinal_repository(
    session: Session = Depends(get_db_session),
) -> SinalRepository:
    return SqlAlchemySinalRepository(session)


def get_alerta_repository(
    session: Session = Depends(get_db_session),
) -> AlertaRepository:
    return SqlAlchemyAlertaRepository(session)


def get_notificacao_repository(
    session: Session = Depends(get_db_session),
) -> NotificacaoRepository:
    return SqlAlchemyNotificacaoRepository(session)


@lru_cache
def _brapi_http_client(base_url: str) -> httpx.Client:
    return httpx.Client(base_url=base_url, timeout=10.0)


def get_brapi_client(settings: Settings = Depends(get_settings)) -> BrapiClient:
    return BrapiClient(_brapi_http_client(settings.brapi_base_url), settings.brapi_api_key or None)


@lru_cache
def _bcb_http_client(base_url: str) -> httpx.Client:
    return httpx.Client(base_url=base_url, timeout=10.0)


def get_bcb_client(settings: Settings = Depends(get_settings)) -> BcbClient:
    return BcbClient(_bcb_http_client(settings.bcb_base_url))


@lru_cache
def _redis_client(redis_url: str) -> redis.Redis:
    return redis.Redis.from_url(redis_url)


def get_mercado_cache(settings: Settings = Depends(get_settings)) -> MercadoCache:
    return RedisMercadoCache(_redis_client(settings.redis_url))


def get_dados_mercado_service(
    brapi_client: BrapiClient = Depends(get_brapi_client),
    mercado_cache: MercadoCache = Depends(get_mercado_cache),
    settings: Settings = Depends(get_settings),
) -> DadosMercadoService:
    return CachedDadosMercadoService(
        DadosMercadoService(brapi_client),
        mercado_cache,
        ttl_cotacao_atual=settings.cache_ttl_cotacao_atual_segundos,
    )


def get_cambio_service(
    bcb_client: BcbClient = Depends(get_bcb_client),
    mercado_cache: MercadoCache = Depends(get_mercado_cache),
    settings: Settings = Depends(get_settings),
) -> CambioService:
    return CachedCambioService(
        BcbCambioService(bcb_client),
        mercado_cache,
        ttl_segundos=settings.cache_ttl_cambio_segundos,
        ttl_fallback_segundos=settings.cache_ttl_cambio_fallback_segundos,
    )


def get_ativo_service(
    ativo_repository: AtivoRepository = Depends(get_ativo_repository),
    dados_mercado_service: DadosMercadoService = Depends(get_dados_mercado_service),
    cotacao_repository: CotacaoRepository = Depends(get_cotacao_repository),
) -> AtivoService:
    return AtivoService(ativo_repository, dados_mercado_service, cotacao_repository)


def get_indicador_service(
    ativo_repository: AtivoRepository = Depends(get_ativo_repository),
    cotacao_repository: CotacaoRepository = Depends(get_cotacao_repository),
    indicador_repository: IndicadorTecnicoRepository = Depends(get_indicador_tecnico_repository),
) -> IndicadorService:
    return IndicadorService(ativo_repository, cotacao_repository, indicador_repository)


def get_sinal_service(
    ativo_repository: AtivoRepository = Depends(get_ativo_repository),
    cotacao_repository: CotacaoRepository = Depends(get_cotacao_repository),
    indicador_service: IndicadorService = Depends(get_indicador_service),
    sinal_repository: SinalRepository = Depends(get_sinal_repository),
) -> SinalService:
    return SinalService(ativo_repository, cotacao_repository, indicador_service, sinal_repository)


def get_watchlist_service(
    watchlist_repository: WatchlistRepository = Depends(get_watchlist_repository),
    ativo_repository: AtivoRepository = Depends(get_ativo_repository),
    dados_mercado_service: DadosMercadoService = Depends(get_dados_mercado_service),
) -> WatchlistService:
    return WatchlistService(watchlist_repository, ativo_repository, dados_mercado_service)


def get_alerta_service(
    alerta_repository: AlertaRepository = Depends(get_alerta_repository),
    ativo_repository: AtivoRepository = Depends(get_ativo_repository),
    dados_mercado_service: DadosMercadoService = Depends(get_dados_mercado_service),
    cambio_service: CambioService = Depends(get_cambio_service),
) -> AlertaService:
    return AlertaService(
        alerta_repository, ativo_repository, dados_mercado_service, cambio_service
    )


def get_operacao_repository(
    session: Session = Depends(get_db_session),
) -> OperacaoRepository:
    return SqlAlchemyOperacaoRepository(session)


def get_portfolio_service(
    operacao_repository: OperacaoRepository = Depends(get_operacao_repository),
    ativo_repository: AtivoRepository = Depends(get_ativo_repository),
    dados_mercado_service: DadosMercadoService = Depends(get_dados_mercado_service),
    cambio_service: CambioService = Depends(get_cambio_service),
    bcb_client: BcbClient = Depends(get_bcb_client),
) -> PortfolioService:
    return PortfolioService(
        operacao_repository, ativo_repository, dados_mercado_service, cambio_service, bcb_client
    )


def get_notificacao_service(
    notificacao_repository: NotificacaoRepository = Depends(get_notificacao_repository),
) -> NotificacaoService:
    return NotificacaoService(notificacao_repository)


def get_usuario_atual(
    credenciais: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    service: UsuarioService = Depends(get_usuario_service),
    settings: Settings = Depends(get_settings),
) -> Usuario:
    try:
        usuario_id = decodificar_token(credenciais.credentials, settings.jwt_secret_key)
    except TokenInvalidoError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token invalido") from exc

    usuario = service.buscar_por_id(usuario_id)
    if usuario is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario nao encontrado")
    return usuario
