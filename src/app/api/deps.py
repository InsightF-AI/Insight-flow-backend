from collections.abc import Generator
from functools import lru_cache

from fastapi import Depends
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.db.session import criar_session_factory
from app.repositories.interfaces.usuario_repository import UsuarioRepository
from app.repositories.sqlalchemy.usuario_repository import SqlAlchemyUsuarioRepository
from app.services.usuario_service import UsuarioService


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
