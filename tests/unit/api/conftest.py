import pytest
from fastapi.testclient import TestClient

from app.api.deps import (
    get_ativo_repository,
    get_cotacao_repository,
    get_dados_mercado_service,
    get_indicador_tecnico_repository,
    get_usuario_repository,
    get_watchlist_repository,
)
from app.main import app
from tests.fixtures.fake_ativo_repository import FakeAtivoRepository
from tests.fixtures.fake_cotacao_repository import FakeCotacaoRepository
from tests.fixtures.fake_dados_mercado_service import FakeDadosMercadoService
from tests.fixtures.fake_indicador_tecnico_repository import FakeIndicadorTecnicoRepository
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
def cotacao_repository() -> FakeCotacaoRepository:
    return FakeCotacaoRepository()


@pytest.fixture
def indicador_repository() -> FakeIndicadorTecnicoRepository:
    return FakeIndicadorTecnicoRepository()


@pytest.fixture
def catalogo_brapi() -> list:
    return []


@pytest.fixture
def cotacoes_brapi() -> dict:
    return {}


@pytest.fixture
def historicos_brapi() -> dict:
    return {}


@pytest.fixture
def dados_mercado_service(
    catalogo_brapi: list, cotacoes_brapi: dict, historicos_brapi: dict
) -> FakeDadosMercadoService:
    return FakeDadosMercadoService(catalogo_brapi, cotacoes_brapi, historicos_brapi)


@pytest.fixture
def client(
    usuario_repository: FakeUsuarioRepository,
    ativo_repository: FakeAtivoRepository,
    watchlist_repository: FakeWatchlistRepository,
    dados_mercado_service: FakeDadosMercadoService,
    cotacao_repository: FakeCotacaoRepository,
    indicador_repository: FakeIndicadorTecnicoRepository,
) -> TestClient:
    app.dependency_overrides[get_usuario_repository] = lambda: usuario_repository
    app.dependency_overrides[get_ativo_repository] = lambda: ativo_repository
    app.dependency_overrides[get_watchlist_repository] = lambda: watchlist_repository
    app.dependency_overrides[get_dados_mercado_service] = lambda: dados_mercado_service
    app.dependency_overrides[get_cotacao_repository] = lambda: cotacao_repository
    app.dependency_overrides[get_indicador_tecnico_repository] = lambda: indicador_repository
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
