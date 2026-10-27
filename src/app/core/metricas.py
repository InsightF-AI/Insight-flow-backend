from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Histogram, start_http_server

ROTA_NAO_MAPEADA = "nao_mapeada"

registro = CollectorRegistry()

requisicoes_http = Counter(
    "insightflow_http_requisicoes_total",
    "Requisicoes HTTP respondidas pela API.",
    ["metodo", "rota", "status"],
    registry=registro,
)
duracao_http = Histogram(
    "insightflow_http_duracao_segundos",
    "Tempo de resposta das requisicoes HTTP.",
    ["metodo", "rota"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
    registry=registro,
)
execucoes_job = Counter(
    "insightflow_job_execucoes_total",
    "Execucoes dos jobs do scheduler, por resultado.",
    ["job", "resultado"],
    registry=registro,
)
duracao_job = Histogram(
    "insightflow_job_duracao_segundos",
    "Tempo de execucao dos jobs do scheduler.",
    ["job"],
    buckets=(0.5, 1, 5, 15, 30, 60, 120, 300, 600),
    registry=registro,
)


def registrar_requisicao(metodo: str, rota: str, status: int, duracao_segundos: float) -> None:
    requisicoes_http.labels(metodo, rota, str(status)).inc()
    duracao_http.labels(metodo, rota).observe(duracao_segundos)


def registrar_job(job: str, sucesso: bool, duracao_segundos: float) -> None:
    execucoes_job.labels(job, "sucesso" if sucesso else "falha").inc()
    duracao_job.labels(job).observe(duracao_segundos)


def iniciar_servidor_metricas(porta: int) -> None:
    start_http_server(porta, registry=registro)
