import json

import httpx
import pytest

from app.integrations.expo.client import (
    ExpoIndisponivelError,
    ExpoPushClient,
    ReciboPush,
    ResultadoEnvio,
)
from app.integrations.retentativa import PoliticaRetentativa


def _client(handler, access_token: str | None = None) -> ExpoPushClient:
    transporte = httpx.MockTransport(handler)
    return ExpoPushClient(
        httpx.Client(base_url="https://exp.host", transport=transporte),
        access_token=access_token,
        politica=PoliticaRetentativa(tentativas=3),
        dormir=lambda _: None,
    )


def _mensagem(token: str) -> dict:
    return {"to": token, "title": "t", "body": "b", "data": {}}


def test_enviar_mapeia_tickets_ok_e_erro_na_ordem():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/--/api/v2/push/send"
        assert len(json.loads(request.content)) == 2
        return httpx.Response(
            200,
            json={
                "data": [
                    {"status": "ok", "id": "ticket-1"},
                    {
                        "status": "error",
                        "message": "not registered",
                        "details": {"error": "DeviceNotRegistered"},
                    },
                ]
            },
        )

    resultados = _client(handler).enviar([_mensagem("A"), _mensagem("B")])

    assert resultados == [
        ResultadoEnvio(token="A", ticket_id="ticket-1", erro=None),
        ResultadoEnvio(token="B", ticket_id=None, erro="DeviceNotRegistered"),
    ]


def test_enviar_erro_sem_detalhe_vira_desconhecido():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"status": "error", "message": "x"}]})

    (resultado,) = _client(handler).enviar([_mensagem("A")])

    assert resultado.erro == "desconhecido"


def test_enviar_divide_em_lotes_de_100():
    tamanhos = []

    def handler(request: httpx.Request) -> httpx.Response:
        lote = json.loads(request.content)
        tamanhos.append(len(lote))
        return httpx.Response(200, json={"data": [{"status": "ok", "id": m["to"]} for m in lote]})

    resultados = _client(handler).enviar([_mensagem(f"T{i}") for i in range(150)])

    assert tamanhos == [100, 50]
    assert [r.ticket_id for r in resultados] == [f"T{i}" for i in range(150)]


def test_enviar_lista_vazia_nao_chama_a_expo():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("nao deveria chamar")

    assert _client(handler).enviar([]) == []


def test_envia_authorization_so_quando_configurado():
    vistos = []

    def handler(request: httpx.Request) -> httpx.Response:
        vistos.append(request.headers.get("Authorization"))
        return httpx.Response(200, json={"data": [{"status": "ok", "id": "x"}]})

    _client(handler).enviar([_mensagem("A")])
    _client(handler, access_token="segredo").enviar([_mensagem("A")])

    assert vistos == [None, "Bearer segredo"]


def test_429_e_retentado_ate_ter_sucesso():
    respostas = iter(
        [
            httpx.Response(429),
            httpx.Response(200, json={"data": [{"status": "ok", "id": "x"}]}),
        ]
    )

    (resultado,) = _client(lambda request: next(respostas)).enviar([_mensagem("A")])

    assert resultado.ticket_id == "x"


def test_erro_http_persistente_vira_expo_indisponivel():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    with pytest.raises(ExpoIndisponivelError):
        _client(handler).enviar([_mensagem("A")])


def test_erros_no_nivel_da_requisicao_viram_expo_indisponivel():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"errors": [{"code": "PUSH_TOO_MANY_EXPERIENCE_IDS", "message": "x"}]}
        )

    with pytest.raises(ExpoIndisponivelError):
        _client(handler).enviar([_mensagem("A")])


@pytest.mark.parametrize(
    "corpo",
    [{}, {"data": None}, {"data": []}, {"data": [{"status": "ok", "id": "1"}]}],
)
def test_resposta_de_envio_inesperada_vira_expo_indisponivel(corpo):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=corpo)

    with pytest.raises(ExpoIndisponivelError):
        _client(handler).enviar([_mensagem("A"), _mensagem("B")])


def test_corpo_que_nao_e_json_vira_expo_indisponivel():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>")

    with pytest.raises(ExpoIndisponivelError):
        _client(handler).enviar([_mensagem("A")])


def test_erro_de_rede_vira_expo_indisponivel():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rede")

    with pytest.raises(ExpoIndisponivelError):
        _client(handler).enviar([_mensagem("A")])


def test_buscar_recibos_mapeia_ok_e_erro_e_omite_ausentes():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/--/api/v2/push/getReceipts"
        assert json.loads(request.content) == {"ids": ["a", "b", "c"]}
        return httpx.Response(
            200,
            json={
                "data": {
                    "a": {"status": "ok"},
                    "b": {"status": "error", "details": {"error": "DeviceNotRegistered"}},
                }
            },
        )

    recibos = _client(handler).buscar_recibos(["a", "b", "c"])

    assert recibos == {
        "a": ReciboPush(status="ok", erro=None),
        "b": ReciboPush(status="error", erro="DeviceNotRegistered"),
    }


def test_buscar_recibos_divide_em_lotes_de_1000():
    tamanhos = []

    def handler(request: httpx.Request) -> httpx.Response:
        tamanhos.append(len(json.loads(request.content)["ids"]))
        return httpx.Response(200, json={"data": {}})

    _client(handler).buscar_recibos([str(i) for i in range(1500)])

    assert tamanhos == [1000, 500]


def test_buscar_recibos_com_data_invalido_vira_expo_indisponivel():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": []})

    with pytest.raises(ExpoIndisponivelError):
        _client(handler).buscar_recibos(["a"])


def test_timeout_no_envio_nao_reenvia_para_nao_duplicar_o_push():
    chamadas = []

    def handler(request: httpx.Request) -> httpx.Response:
        chamadas.append(request)
        raise httpx.ReadTimeout("lento", request=request)

    with pytest.raises(ExpoIndisponivelError):
        _client(handler).enviar([_mensagem("A")])

    assert len(chamadas) == 1


def test_falha_de_conexao_no_envio_e_retentada():
    respostas = iter([httpx.ConnectError("sem rede"), None])

    def handler(request: httpx.Request) -> httpx.Response:
        erro = next(respostas)
        if erro is not None:
            raise erro
        return httpx.Response(200, json={"data": [{"status": "ok", "id": "x"}]})

    (resultado,) = _client(handler).enviar([_mensagem("A")])

    assert resultado.ticket_id == "x"


def test_timeout_na_consulta_de_recibos_e_retentado():
    chamadas = []

    def handler(request: httpx.Request) -> httpx.Response:
        chamadas.append(request)
        if len(chamadas) == 1:
            raise httpx.ReadTimeout("lento", request=request)
        return httpx.Response(200, json={"data": {}})

    assert _client(handler).buscar_recibos(["a"]) == {}
    assert len(chamadas) == 2
