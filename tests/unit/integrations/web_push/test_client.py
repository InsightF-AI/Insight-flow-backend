import json
import logging
from datetime import UTC, datetime

import httpx
import pytest

from app.core.config import Settings
from app.integrations.retentativa import PoliticaRetentativa
from app.integrations.web_push.client import (
    ResultadoWebPush,
    WebPushClient,
    WebPushIndisponivelError,
)
from app.integrations.web_push.fabrica import criar_web_push_client
from app.integrations.web_push.vapid import ChaveVapid
from tests.fixtures.navegador_falso import NavegadorFalso

_AGORA = datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
_ENDPOINT = "https://fcm.googleapis.com/fcm/send/abc"
_PAYLOAD = {"title": "Alerta de preço", "body": "PETR4", "data": {"tipo": "ALERTA_DISPARADO"}}


def _client(handler) -> WebPushClient:
    return WebPushClient(
        httpx.Client(transport=httpx.MockTransport(handler)),
        ChaveVapid.gerar(),
        "mailto:equipe@exemplo.com",
        86400,
        politica=PoliticaRetentativa(tentativas=3),
        dormir=lambda _: None,
        agora=lambda: _AGORA,
    )


def _enviar(handler, navegador: NavegadorFalso | None = None) -> ResultadoWebPush:
    navegador = navegador or NavegadorFalso()
    return _client(handler).enviar(_ENDPOINT, navegador.p256dh, navegador.auth, _PAYLOAD)


def test_envia_corpo_cifrado_e_headers_do_protocolo():
    navegador = NavegadorFalso()
    vistos = []

    def handler(request: httpx.Request) -> httpx.Response:
        vistos.append(request)
        return httpx.Response(201)

    resultado = _enviar(handler, navegador)

    assert resultado is ResultadoWebPush.ENTREGUE
    (request,) = vistos
    assert str(request.url) == _ENDPOINT
    assert request.headers["Content-Encoding"] == "aes128gcm"
    assert request.headers["Content-Type"] == "application/octet-stream"
    assert request.headers["TTL"] == "86400"
    assert request.headers["Urgency"] == "high"
    assert request.headers["Authorization"].startswith("vapid t=")
    assert json.loads(navegador.decifrar(request.content)) == _PAYLOAD


@pytest.mark.parametrize("status", [200, 201, 202])
def test_2xx_e_entregue(status):
    assert _enviar(lambda request: httpx.Response(status)) is ResultadoWebPush.ENTREGUE


@pytest.mark.parametrize("status", [404, 410])
def test_404_e_410_sao_inscricao_expirada(status):
    resultado = _enviar(lambda request: httpx.Response(status))

    assert resultado is ResultadoWebPush.INSCRICAO_EXPIRADA


def test_401_e_recusado_com_log_de_erro(caplog):
    caplog.set_level(logging.INFO)

    resultado = _enviar(lambda request: httpx.Response(401))

    assert resultado is ResultadoWebPush.RECUSADO
    registro = next(r for r in caplog.records if getattr(r, "evento", None) == "push_web_recusado")
    assert registro.levelno == logging.ERROR
    assert registro.host == "fcm.googleapis.com"
    assert _ENDPOINT not in str(vars(registro))


def test_413_e_recusado_com_aviso(caplog):
    caplog.set_level(logging.INFO)

    assert _enviar(lambda request: httpx.Response(413)) is ResultadoWebPush.RECUSADO
    assert any(r.levelno == logging.WARNING for r in caplog.records)


def test_redirect_nao_e_seguido_e_vira_recusado():
    vistos = []

    def handler(request: httpx.Request) -> httpx.Response:
        vistos.append(str(request.url))
        return httpx.Response(302, headers={"Location": "https://169.254.169.254/"})

    assert _enviar(handler) is ResultadoWebPush.RECUSADO
    assert vistos == [_ENDPOINT]


def test_429_e_retentado():
    respostas = iter([httpx.Response(429), httpx.Response(201)])

    assert _enviar(lambda request: next(respostas)) is ResultadoWebPush.ENTREGUE


def test_5xx_persistente_vira_indisponivel():
    with pytest.raises(WebPushIndisponivelError):
        _enviar(lambda request: httpx.Response(503))


def test_timeout_nao_e_reenviado():
    vistos = []

    def handler(request: httpx.Request) -> httpx.Response:
        vistos.append(request)
        raise httpx.ReadTimeout("lento", request=request)

    with pytest.raises(WebPushIndisponivelError):
        _enviar(handler)

    assert len(vistos) == 1


def test_falha_de_conexao_e_retentada():
    respostas = iter([httpx.ConnectError("sem rede"), None])

    def handler(request: httpx.Request) -> httpx.Response:
        erro = next(respostas)
        if erro is not None:
            raise erro
        return httpx.Response(201)

    assert _enviar(handler) is ResultadoWebPush.ENTREGUE


def test_fabrica_devolve_none_sem_configuracao():
    assert criar_web_push_client(Settings(_env_file=None)) is None


def test_fabrica_devolve_cliente_quando_configurado():
    settings = Settings(
        _env_file=None,
        web_push_vapid_chave_privada=ChaveVapid.gerar().privada_base64url(),
        web_push_vapid_contato="mailto:a@b.c",
    )

    assert isinstance(criar_web_push_client(settings), WebPushClient)
