import logging

from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.testclient import TestClient

from app.api.correlacao import CorrelacaoMiddleware, registrar_usuario_na_requisicao
from app.core.logs import correlation_id_atual, id_de_correlacao_valido


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(CorrelacaoMiddleware)

    @app.get("/eco")
    def eco():
        logging.getLogger("app.teste").info("Dentro da rota.")
        return {"correlation_id": correlation_id_atual()}

    @app.get("/autenticada")
    def autenticada(request: Request):
        registrar_usuario_na_requisicao(request, "usuario-1")
        return {}

    @app.get("/falha")
    def falha():
        raise HTTPException(404, "nao achei")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.websocket("/ws")
    async def ws(websocket: WebSocket):
        await websocket.accept()
        await websocket.send_json({"correlation_id": correlation_id_atual()})
        await websocket.close()

    return app


def _registros_de_requisicao(caplog) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == "app.api.correlacao"]


def test_gera_correlation_id_e_devolve_no_header():
    resposta = TestClient(_app()).get("/eco")

    gerado = resposta.headers["X-Request-ID"]
    assert id_de_correlacao_valido(gerado)
    assert resposta.json()["correlation_id"] == gerado


def test_reaproveita_o_x_request_id_valido_do_cliente():
    resposta = TestClient(_app()).get("/eco", headers={"X-Request-ID": "cliente-123"})

    assert resposta.headers["X-Request-ID"] == "cliente-123"
    assert resposta.json()["correlation_id"] == "cliente-123"


def test_ignora_x_request_id_invalido():
    resposta = TestClient(_app()).get("/eco", headers={"X-Request-ID": "x" * 100})

    assert resposta.headers["X-Request-ID"] != "x" * 100
    assert id_de_correlacao_valido(resposta.headers["X-Request-ID"])


def test_logs_dentro_da_rota_carregam_o_correlation_id(caplog):
    caplog.set_level(logging.INFO)

    resposta = TestClient(_app()).get("/eco")

    registro = next(r for r in caplog.records if r.getMessage() == "Dentro da rota.")
    assert registro.correlation_id == resposta.headers["X-Request-ID"]


def test_loga_a_requisicao_com_metodo_caminho_status_e_duracao(caplog):
    caplog.set_level(logging.INFO)

    TestClient(_app()).get("/falha")

    registro = _registros_de_requisicao(caplog)[-1]
    assert registro.metodo == "GET"
    assert registro.caminho == "/falha"
    assert registro.status == 404
    assert registro.duracao_ms >= 0
    assert registro.usuario_id is None


def test_loga_o_usuario_autenticado(caplog):
    caplog.set_level(logging.INFO)

    TestClient(_app()).get("/autenticada")

    assert _registros_de_requisicao(caplog)[-1].usuario_id == "usuario-1"


def test_nao_loga_o_health_check(caplog):
    caplog.set_level(logging.INFO)

    TestClient(_app()).get("/health")

    assert _registros_de_requisicao(caplog) == []


def test_websocket_recebe_um_correlation_id_por_conexao():
    with TestClient(_app()).websocket_connect("/ws") as conexao:
        recebido = conexao.receive_json()

    assert id_de_correlacao_valido(recebido["correlation_id"])


def test_erro_nao_tratado_e_logado_com_status_500(caplog):
    app = _app()

    @app.get("/explode")
    def explode():
        raise RuntimeError("bug")

    caplog.set_level(logging.INFO)
    resposta = TestClient(app, raise_server_exceptions=False).get("/explode")

    assert resposta.status_code == 500
    assert resposta.json() == {"detail": "Internal Server Error"}
    assert id_de_correlacao_valido(resposta.headers["X-Request-ID"])
    registro = _registros_de_requisicao(caplog)[-1]
    assert registro.status == 500
    assert registro.levelno == logging.ERROR
    assert registro.exc_info is not None
    assert registro.correlation_id == resposta.headers["X-Request-ID"]
