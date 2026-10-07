from uuid import uuid4

import pytest
from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials

from app.api.deps import (
    get_binance_client,
    get_brapi_client,
    get_dados_mercado_service,
    get_notificacao_service,
    get_usuario_atual,
)
from app.core.config import Settings
from app.core.security import criar_token
from app.domain.entities.usuario import Usuario
from app.services.cached_dados_mercado_service import CachedDadosMercadoService
from app.services.roteador_dados_mercado_service import RoteadorDadosMercadoService
from app.services.usuario_service import UsuarioService
from tests.fixtures.fake_barramento_notificacoes import FakeBarramentoNotificacoes
from tests.fixtures.fake_dispositivo_push_repository import FakeDispositivoPushRepository
from tests.fixtures.fake_inscricao_web_push_repository import FakeInscricaoWebPushRepository
from tests.fixtures.fake_mercado_cache import FakeMercadoCache
from tests.fixtures.fake_notificacao_repository import FakeNotificacaoRepository
from tests.fixtures.fake_ticket_push_repository import FakeTicketPushRepository
from tests.fixtures.fake_usuario_repository import FakeUsuarioRepository

SETTINGS = Settings(jwt_secret_key="segredo-de-teste", jwt_expiration_minutes=60)


def _service_com_usuario() -> tuple[UsuarioService, Usuario]:
    service = UsuarioService(FakeUsuarioRepository())
    usuario = service.cadastrar(nome="Ana", email="ana@example.com", senha="segredo123")
    return service, usuario


def _requisicao() -> Request:
    return Request({"type": "http", "state": {}})


def _credenciais(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_token_valido_retorna_o_usuario_correspondente():
    service, usuario = _service_com_usuario()
    token = criar_token(usuario.id, SETTINGS.jwt_secret_key, SETTINGS.jwt_expiration_minutes)
    requisicao = _requisicao()

    encontrado = get_usuario_atual(requisicao, _credenciais(token), service, SETTINGS)

    assert encontrado.id == usuario.id
    assert requisicao.scope["state"]["usuario_id_log"] == str(usuario.id)


def test_token_com_assinatura_invalida_lanca_401():
    service, usuario = _service_com_usuario()
    token = criar_token(usuario.id, "outro-segredo", SETTINGS.jwt_expiration_minutes)

    with pytest.raises(HTTPException) as exc_info:
        get_usuario_atual(_requisicao(), _credenciais(token), service, SETTINGS)

    assert exc_info.value.status_code == 401


def test_token_de_usuario_inexistente_lanca_401():
    service, _ = _service_com_usuario()
    token = criar_token(uuid4(), SETTINGS.jwt_secret_key, SETTINGS.jwt_expiration_minutes)

    with pytest.raises(HTTPException) as exc_info:
        get_usuario_atual(_requisicao(), _credenciais(token), service, SETTINGS)

    assert exc_info.value.status_code == 401


def test_get_provedor_llm_sem_configuracao_lanca_503():
    from app.api.deps import get_provedor_llm

    with pytest.raises(HTTPException) as exc_info:
        get_provedor_llm(Settings(_env_file=None))

    assert exc_info.value.status_code == 503


def test_get_provedor_llm_configurado_retorna_gemini():
    from app.ai.providers.gemini import GeminiProvider
    from app.api.deps import get_provedor_llm

    provedor = get_provedor_llm(
        Settings(_env_file=None, ai_habilitada=True, gemini_api_key="chave")
    )

    assert isinstance(provedor, GeminiProvider)


def test_dados_mercado_service_envolve_o_roteador_no_cache():
    settings = Settings(_env_file=None)
    cache = FakeMercadoCache()

    service = get_dados_mercado_service(
        brapi_client=get_brapi_client(settings),
        binance_client=get_binance_client(settings),
        mercado_cache=cache,
        settings=settings,
    )

    assert isinstance(service, CachedDadosMercadoService)
    assert isinstance(service._interno, RoteadorDadosMercadoService)


def test_notificacao_service_publica_no_barramento_e_inclui_o_canal_expo():
    barramento = FakeBarramentoNotificacoes()

    service = get_notificacao_service(
        notificacao_repository=FakeNotificacaoRepository(),
        barramento=barramento,
        dispositivo_repository=FakeDispositivoPushRepository(),
        ticket_repository=FakeTicketPushRepository(),
        inscricao_repository=FakeInscricaoWebPushRepository(),
        settings=Settings(_env_file=None),
    )
    notificacao = service.enviar_resumo_diario(uuid4(), "Resumo", {})

    assert barramento.publicados[0][0] == notificacao.usuario_id
    assert [type(c).__name__ for c in service._canais] == ["CanalTempoReal", "CanalExpo"]
