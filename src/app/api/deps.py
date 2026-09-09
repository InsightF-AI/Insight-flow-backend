from collections.abc import Generator
from functools import lru_cache

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.core.security import TokenInvalidoError, decodificar_token
from app.db.session import criar_session_factory
from app.domain.entities.usuario import Usuario
from app.integrations.brapi.client import BrapiClient
from app.repositories.interfaces.ativo_repository import AtivoRepository
from app.repositories.interfaces.usuario_repository import UsuarioRepository
from app.repositories.interfaces.watchlist_repository import WatchlistRepository
from app.repositories.sqlalchemy.ativo_repository import SqlAlchemyAtivoRepository
from app.repositories.sqlalchemy.usuario_repository import SqlAlchemyUsuarioRepository
from app.repositories.sqlalchemy.watchlist_repository import SqlAlchemyWatchlistRepository
from app.services.dados_mercado_service import DadosMercadoService
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


@lru_cache
def _brapi_http_client(base_url: str) -> httpx.Client:
    return httpx.Client(base_url=base_url, timeout=10.0)


def get_brapi_client(settings: Settings = Depends(get_settings)) -> BrapiClient:
    return BrapiClient(_brapi_http_client(settings.brapi_base_url), settings.brapi_api_key or None)


def get_dados_mercado_service(
    brapi_client: BrapiClient = Depends(get_brapi_client),
) -> DadosMercadoService:
    return DadosMercadoService(brapi_client)


def get_watchlist_service(
    watchlist_repository: WatchlistRepository = Depends(get_watchlist_repository),
    ativo_repository: AtivoRepository = Depends(get_ativo_repository),
    dados_mercado_service: DadosMercadoService = Depends(get_dados_mercado_service),
) -> WatchlistService:
    return WatchlistService(watchlist_repository, ativo_repository, dados_mercado_service)


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
