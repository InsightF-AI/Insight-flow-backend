from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.api.deps import (
    get_analise_ia_repository,
    get_ativo_repository,
    get_barramento_notificacoes,
    get_cotacao_repository,
    get_dados_mercado_service,
    get_dispositivo_push_repository,
    get_indicador_tecnico_repository,
    get_inscricao_web_push_repository,
    get_operacao_repository,
    get_portfolio_service,
    get_provedor_llm,
    get_refresh_token_repository,
    get_sinal_repository,
    get_ticket_push_repository,
    get_usuario_repository,
    get_watchlist_repository,
)
from app.main import app
from app.services.portfolio_service import PortfolioService
from tests.fixtures.fake_analise_ia_repository import FakeAnaliseIARepository
from tests.fixtures.fake_ativo_repository import FakeAtivoRepository
from tests.fixtures.fake_barramento_notificacoes import FakeBarramentoNotificacoes
from tests.fixtures.fake_cambio_service import FakeCambioService
from tests.fixtures.fake_cotacao_repository import FakeCotacaoRepository
from tests.fixtures.fake_dados_mercado_service import FakeDadosMercadoService
from tests.fixtures.fake_dispositivo_push_repository import FakeDispositivoPushRepository
from tests.fixtures.fake_indicador_tecnico_repository import FakeIndicadorTecnicoRepository
from tests.fixtures.fake_inscricao_web_push_repository import FakeInscricaoWebPushRepository
from tests.fixtures.fake_operacao_repository import FakeOperacaoRepository
from tests.fixtures.fake_provedor_llm import FakeProvedorLLM
from tests.fixtures.fake_refresh_token_repository import FakeRefreshTokenRepository
from tests.fixtures.fake_sinal_repository import FakeSinalRepository
from tests.fixtures.fake_ticket_push_repository import FakeTicketPushRepository
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
def sinal_repository() -> FakeSinalRepository:
    return FakeSinalRepository()


@pytest.fixture
def operacao_repository() -> FakeOperacaoRepository:
    return FakeOperacaoRepository()


@pytest.fixture
def provedor_llm() -> FakeProvedorLLM:
    return FakeProvedorLLM()


@pytest.fixture
def analise_repository() -> FakeAnaliseIARepository:
    return FakeAnaliseIARepository()


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
def barramento_notificacoes() -> FakeBarramentoNotificacoes:
    return FakeBarramentoNotificacoes()


@pytest.fixture
def refresh_token_repository() -> FakeRefreshTokenRepository:
    return FakeRefreshTokenRepository()


@pytest.fixture
def dispositivo_push_repository() -> FakeDispositivoPushRepository:
    return FakeDispositivoPushRepository()


@pytest.fixture
def ticket_push_repository() -> FakeTicketPushRepository:
    return FakeTicketPushRepository()


@pytest.fixture
def inscricao_web_push_repository() -> FakeInscricaoWebPushRepository:
    return FakeInscricaoWebPushRepository()


@pytest.fixture
def client(
    usuario_repository: FakeUsuarioRepository,
    ativo_repository: FakeAtivoRepository,
    watchlist_repository: FakeWatchlistRepository,
    dados_mercado_service: FakeDadosMercadoService,
    cotacao_repository: FakeCotacaoRepository,
    indicador_repository: FakeIndicadorTecnicoRepository,
    sinal_repository: FakeSinalRepository,
    operacao_repository: FakeOperacaoRepository,
    provedor_llm: FakeProvedorLLM,
    analise_repository: FakeAnaliseIARepository,
    refresh_token_repository: FakeRefreshTokenRepository,
    barramento_notificacoes: FakeBarramentoNotificacoes,
    dispositivo_push_repository: FakeDispositivoPushRepository,
    ticket_push_repository: FakeTicketPushRepository,
    inscricao_web_push_repository: FakeInscricaoWebPushRepository,
) -> TestClient:
    app.dependency_overrides[get_usuario_repository] = lambda: usuario_repository
    app.dependency_overrides[get_ativo_repository] = lambda: ativo_repository
    app.dependency_overrides[get_watchlist_repository] = lambda: watchlist_repository
    app.dependency_overrides[get_dados_mercado_service] = lambda: dados_mercado_service
    app.dependency_overrides[get_cotacao_repository] = lambda: cotacao_repository
    app.dependency_overrides[get_indicador_tecnico_repository] = lambda: indicador_repository
    app.dependency_overrides[get_sinal_repository] = lambda: sinal_repository
    app.dependency_overrides[get_operacao_repository] = lambda: operacao_repository
    app.dependency_overrides[get_portfolio_service] = lambda: PortfolioService(
        operacao_repository,
        ativo_repository,
        dados_mercado_service,
        FakeCambioService(taxa=Decimal(1)),
        None,
        cotacao_repository,
    )
    app.dependency_overrides[get_provedor_llm] = lambda: provedor_llm
    app.dependency_overrides[get_analise_ia_repository] = lambda: analise_repository
    app.dependency_overrides[get_refresh_token_repository] = lambda: refresh_token_repository
    app.dependency_overrides[get_barramento_notificacoes] = lambda: barramento_notificacoes
    app.dependency_overrides[get_dispositivo_push_repository] = lambda: dispositivo_push_repository
    app.dependency_overrides[get_ticket_push_repository] = lambda: ticket_push_repository
    app.dependency_overrides[get_inscricao_web_push_repository] = lambda: (
        inscricao_web_push_repository
    )
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
