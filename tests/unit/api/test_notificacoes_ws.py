import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from starlette.websockets import WebSocketDisconnect

from app.api.deps import get_barramento_notificacoes, get_buscador_usuario
from app.core.config import Settings, get_settings
from app.core.security import criar_token
from app.domain.entities.alerta_personalizado import AlertaPersonalizado
from app.domain.entities.usuario import Usuario
from app.domain.enums.tipo_condicao_alerta import TipoCondicaoAlerta
from app.integrations.brapi.client import CotacaoAtual
from app.main import app
from app.notifications.canal import CanalTempoReal
from app.services.notificacao_service import NotificacaoService
from tests.fixtures.fake_barramento_notificacoes import FakeBarramentoNotificacoes
from tests.fixtures.fake_notificacao_repository import FakeNotificacaoRepository
from tests.fixtures.fake_usuario_repository import FakeUsuarioRepository

_SEGREDO = "segredo-ws"
_URL = "/api/v1/notificacoes/ws"


class _Ambiente:
    def __init__(self, timeout_autenticacao: float = 1.0, intervalo_ping: float = 60.0):
        self.usuarios = FakeUsuarioRepository()
        self.barramento = FakeBarramentoNotificacoes()
        settings = Settings(
            _env_file=None,
            jwt_secret_key=_SEGREDO,
            ws_timeout_autenticacao_segundos=timeout_autenticacao,
            ws_intervalo_ping_segundos=intervalo_ping,
        )
        app.dependency_overrides[get_settings] = lambda: settings
        app.dependency_overrides[get_barramento_notificacoes] = lambda: self.barramento
        app.dependency_overrides[get_buscador_usuario] = lambda: self.usuarios.buscar_por_id
        self.client = TestClient(app)

    def novo_usuario(self, ativo: bool = True) -> Usuario:
        usuario = Usuario.criar(
            id=uuid4(),
            nome="Ana",
            email=f"ana-{uuid4()}@example.com",
            senha="segredo123",
            criado_em=datetime.now(UTC),
        )
        usuario.ativo = ativo
        self.usuarios.salvar(usuario)
        return usuario


@pytest.fixture
def ambiente():
    yield _Ambiente()
    app.dependency_overrides.clear()


@pytest.fixture
def ambiente_rapido():
    yield _Ambiente(timeout_autenticacao=0.2, intervalo_ping=0.2)
    app.dependency_overrides.clear()


def _token(usuario: Usuario) -> str:
    return criar_token(usuario.id, _SEGREDO, expiracao_minutos=30)


def _autenticar(ws, token: str) -> dict:
    ws.send_json({"tipo": "autenticar", "token": token})
    return ws.receive_json()


def _espera_fechamento_4401(ws) -> None:
    with pytest.raises(WebSocketDisconnect) as erro:
        ws.receive_json()
    assert erro.value.code == 4401


def _publicar_para(ambiente: _Ambiente, usuario_id) -> None:
    ambiente.barramento.publicar(usuario_id, {"tipo": "notificacao", "notificacao": {"id": "x"}})


def test_token_valido_recebe_autenticado(ambiente):
    usuario = ambiente.novo_usuario()

    with ambiente.client.websocket_connect(_URL) as ws:
        assert _autenticar(ws, _token(usuario)) == {"tipo": "autenticado"}


def test_token_invalido_fecha_4401(ambiente):
    with ambiente.client.websocket_connect(_URL) as ws:
        ws.send_json({"tipo": "autenticar", "token": "lixo"})
        _espera_fechamento_4401(ws)


def test_usuario_inativo_fecha_4401(ambiente):
    usuario = ambiente.novo_usuario(ativo=False)

    with ambiente.client.websocket_connect(_URL) as ws:
        ws.send_json({"tipo": "autenticar", "token": _token(usuario)})
        _espera_fechamento_4401(ws)


def test_primeira_mensagem_que_nao_e_autenticar_fecha_4401(ambiente):
    with ambiente.client.websocket_connect(_URL) as ws:
        ws.send_json({"tipo": "outra"})
        _espera_fechamento_4401(ws)


def test_primeira_mensagem_que_nao_e_json_fecha_4401(ambiente):
    with ambiente.client.websocket_connect(_URL) as ws:
        ws.send_text("isto nao e json")
        _espera_fechamento_4401(ws)


def test_silencio_alem_do_prazo_fecha_4401(ambiente_rapido):
    with ambiente_rapido.client.websocket_connect(_URL) as ws:
        _espera_fechamento_4401(ws)


def test_notificacao_do_usuario_chega_e_a_de_outro_nao(ambiente):
    usuario = ambiente.novo_usuario()
    outro = ambiente.novo_usuario()

    with ambiente.client.websocket_connect(_URL) as ws:
        _autenticar(ws, _token(usuario))
        _publicar_para(ambiente, outro.id)
        ambiente.barramento.publicar(
            usuario.id, {"tipo": "notificacao", "notificacao": {"id": "meu"}}
        )

        assert ws.receive_json() == {"tipo": "notificacao", "notificacao": {"id": "meu"}}


def test_dois_sockets_do_mesmo_usuario_recebem_a_mesma_notificacao(ambiente):
    usuario = ambiente.novo_usuario()

    with (
        ambiente.client.websocket_connect(_URL) as web,
        ambiente.client.websocket_connect(_URL) as desktop,
    ):
        _autenticar(web, _token(usuario))
        _autenticar(desktop, _token(usuario))
        _publicar_para(ambiente, usuario.id)

        assert web.receive_json()["notificacao"] == {"id": "x"}
        assert desktop.receive_json()["notificacao"] == {"id": "x"}


def test_ping_chega_no_intervalo(ambiente_rapido):
    usuario = ambiente_rapido.novo_usuario()

    with ambiente_rapido.client.websocket_connect(_URL) as ws:
        _autenticar(ws, _token(usuario))

        assert ws.receive_json() == {"tipo": "ping"}


def test_reautenticacao_com_token_novo_mantem_a_conexao(ambiente):
    usuario = ambiente.novo_usuario()

    with ambiente.client.websocket_connect(_URL) as ws:
        _autenticar(ws, _token(usuario))

        assert _autenticar(ws, _token(usuario)) == {"tipo": "autenticado"}
        _publicar_para(ambiente, usuario.id)
        assert ws.receive_json()["tipo"] == "notificacao"


def test_reautenticacao_com_token_invalido_fecha_4401(ambiente):
    usuario = ambiente.novo_usuario()

    with ambiente.client.websocket_connect(_URL) as ws:
        _autenticar(ws, _token(usuario))
        ws.send_json({"tipo": "autenticar", "token": "lixo"})
        _espera_fechamento_4401(ws)


def test_reautenticacao_com_token_de_outro_usuario_fecha_4401(ambiente):
    usuario = ambiente.novo_usuario()
    outro = ambiente.novo_usuario()

    with ambiente.client.websocket_connect(_URL) as ws:
        _autenticar(ws, _token(usuario))
        ws.send_json({"tipo": "autenticar", "token": _token(outro)})
        _espera_fechamento_4401(ws)


def test_token_que_expira_sem_reautenticacao_fecha_4401(ambiente):
    usuario = ambiente.novo_usuario()
    token_curto = jwt.encode(
        {"sub": str(usuario.id), "exp": datetime.now(UTC) + timedelta(seconds=1)},
        _SEGREDO,
        algorithm="HS256",
    )

    with ambiente.client.websocket_connect(_URL) as ws:
        assert _autenticar(ws, token_curto) == {"tipo": "autenticado"}
        _espera_fechamento_4401(ws)


def test_desconexao_fecha_a_assinatura(ambiente):
    usuario = ambiente.novo_usuario()

    with ambiente.client.websocket_connect(_URL) as ws:
        _autenticar(ws, _token(usuario))
        assert ambiente.barramento.total_assinantes(usuario.id) == 1

    for _ in range(50):
        if ambiente.barramento.total_assinantes(usuario.id) == 0:
            break
        time.sleep(0.02)
    assert ambiente.barramento.total_assinantes(usuario.id) == 0


def test_alerta_disparado_pelo_service_chega_ao_socket_do_dono(ambiente):
    usuario = ambiente.novo_usuario()
    service = NotificacaoService(
        FakeNotificacaoRepository(), canais=[CanalTempoReal(ambiente.barramento)]
    )
    alerta = AlertaPersonalizado.criar(
        id=uuid4(),
        usuario_id=usuario.id,
        ativo_id=uuid4(),
        tipo_condicao=TipoCondicaoAlerta.PRECO_MAIOR_IGUAL,
        valor_alvo=Decimal("40.00"),
        moeda_alvo="BRL",
        criado_em=datetime.now(UTC),
    )
    cotacao = CotacaoAtual(
        ticker="PETR4",
        preco=Decimal("41.00"),
        variacao=Decimal(0),
        variacao_percentual=Decimal(0),
        maxima_dia=Decimal("41.00"),
        minima_dia=Decimal("41.00"),
        volume=Decimal(1),
    )

    with ambiente.client.websocket_connect(_URL) as ws:
        _autenticar(ws, _token(usuario))
        notificacao = service.enviar_alerta_personalizado(usuario.id, alerta, cotacao)

        mensagem = ws.receive_json()

    assert mensagem["tipo"] == "notificacao"
    assert mensagem["notificacao"]["id"] == str(notificacao.id)
    assert mensagem["notificacao"]["tipo"] == "ALERTA_DISPARADO"
    assert "PETR4" in mensagem["notificacao"]["mensagem"]


def test_primeira_mensagem_binaria_fecha_4401(ambiente):
    with ambiente.client.websocket_connect(_URL) as ws:
        ws.send_bytes(b"\x00\x01")
        _espera_fechamento_4401(ws)


def test_mensagem_binaria_depois_de_autenticado_e_ignorada(ambiente):
    usuario = ambiente.novo_usuario()

    with ambiente.client.websocket_connect(_URL) as ws:
        _autenticar(ws, _token(usuario))
        ws.send_bytes(b"\x00\x01")
        _publicar_para(ambiente, usuario.id)

        assert ws.receive_json()["tipo"] == "notificacao"
