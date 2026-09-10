import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models.ativo import AtivoModel
from app.db.models.cotacao import CotacaoModel
from app.db.models.usuario import UsuarioModel
from app.db.models.watchlist import WatchlistModel

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://insightflow:insightflow@localhost:5432/insightflow_test",
)


@pytest.fixture(scope="session")
def engine():
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def session(engine):
    connection = engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection, join_transaction_mode="create_savepoint")
    session = session_factory()

    yield session

    session.close()
    transaction.rollback()
    connection.close()
