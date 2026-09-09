import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_usuario_repository
from app.main import app
from tests.fixtures.fake_usuario_repository import FakeUsuarioRepository


@pytest.fixture
def usuario_repository() -> FakeUsuarioRepository:
    return FakeUsuarioRepository()


@pytest.fixture
def client(usuario_repository: FakeUsuarioRepository) -> TestClient:
    app.dependency_overrides[get_usuario_repository] = lambda: usuario_repository
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
