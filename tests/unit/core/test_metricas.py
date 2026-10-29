from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.correlacao import CorrelacaoMiddleware
from app.core.metricas import registro
from app.scheduler.execucao import executar_job


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(CorrelacaoMiddleware)

    @app.get("/metricas-teste/{ticker}")
    def item(ticker: str):
        return {"ticker": ticker}

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


def _requisicoes(rota: str, status: str) -> float:
    valor = registro.get_sample_value(
        "insightflow_http_requisicoes_total", {"metodo": "GET", "rota": rota, "status": status}
    )
    return valor or 0.0


def _execucoes(job: str, resultado: str) -> float:
    valor = registro.get_sample_value(
        "insightflow_job_execucoes_total", {"job": job, "resultado": resultado}
    )
    return valor or 0.0


def test_conta_a_requisicao_pelo_template_da_rota_e_nao_pelo_caminho():
    antes = _requisicoes("/metricas-teste/{ticker}", "200")

    client = TestClient(_app())
    client.get("/metricas-teste/PETR4")
    client.get("/metricas-teste/VALE3")

    assert _requisicoes("/metricas-teste/{ticker}", "200") == antes + 2
    assert _requisicoes("/metricas-teste/PETR4", "200") == 0


def test_caminho_sem_rota_entra_como_nao_mapeada():
    antes = _requisicoes("nao_mapeada", "404")

    TestClient(_app()).get("/nao-existe/qualquer-coisa")

    assert _requisicoes("nao_mapeada", "404") == antes + 1


def test_registra_a_duracao_da_requisicao():
    rotulos = {"metodo": "GET", "rota": "/metricas-teste/{ticker}"}
    antes = registro.get_sample_value("insightflow_http_duracao_segundos_count", rotulos) or 0

    TestClient(_app()).get("/metricas-teste/ITUB4")

    assert (
        registro.get_sample_value("insightflow_http_duracao_segundos_count", rotulos) == antes + 1
    )


def test_health_check_nao_entra_nas_metricas():
    antes = _requisicoes("/health", "200")

    TestClient(_app()).get("/health")

    assert _requisicoes("/health", "200") == antes


def test_conta_execucoes_de_job_por_resultado():
    sucesso_antes = _execucoes("job_metricas_teste", "sucesso")
    falha_antes = _execucoes("job_metricas_teste", "falha")

    def falhar():
        raise RuntimeError("boom")

    executar_job("job_metricas_teste", lambda: None)
    executar_job("job_metricas_teste", falhar)

    assert _execucoes("job_metricas_teste", "sucesso") == sucesso_antes + 1
    assert _execucoes("job_metricas_teste", "falha") == falha_antes + 1
