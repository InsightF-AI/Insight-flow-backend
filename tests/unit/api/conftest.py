import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_ativo_repository, get_usuario_repository, get_watchlist_repository
from app.main import app
from tests.fixtures.fake_ativo_repository import FakeAtivoRepository
from tests.fixtures.fake_usuario_repository import FakeUsuarioRepository
from tests.fixtures.fake_watchlist_repository import FakeWatchlistRepository


@pytest.fixture
def usuario_repository() -> FakeUsuarioRepository:
    return FakeUsuarioRepository()


@pytest.fixture
def ativo_repository() -> FakeAtivoRepository:
    return FakeAtivoRepository()


@pytest.fixture
def watchlist_repository() -> FakeWatchlistRepository:
    return FakeWatchlistRepository()


@pytest.fixture
def client(
    usuario_repository: FakeUsuarioRepository,
    ativo_repository: FakeAtivoRepository,
    watchlist_repository: FakeWatchlistRepository,
) -> TestClient:
    app.dependency_overrides[get_usuario_repository] = lambda: usuario_repository
    app.dependency_overrides[get_ativo_repository] = lambda: ativo_repository
    app.dependency_overrides[get_watchlist_repository] = lambda: watchlist_repository
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _headers_para(client: TestClient, email: str) -> dict[str, str]:
    resposta = client.post(
        "/api/v1/usuarios",
        json={"nome": "Usuario Teste", "email": email, "senha": "segredo123"},
    )
    token = resposta.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers(client: TestClient) -> dict[str, str]:
    return _headers_para(client, "ana@example.com")


@pytest.fixture
def auth_headers_outro_usuario(client: TestClient) -> dict[str, str]:
    return _headers_para(client, "bruno@example.com")
