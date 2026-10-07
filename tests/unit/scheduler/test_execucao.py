import logging

from app.core.logs import correlation_id_atual, id_de_correlacao_valido
from app.scheduler.execucao import executar_job


def _registros(caplog):
    return [r for r in caplog.records if r.name == "app.scheduler.execucao"]


def test_job_roda_com_correlation_id_proprio_e_loga_inicio_e_fim(caplog):
    vistos = []
    caplog.set_level(logging.INFO)

    executar_job("ciclo_cripto", lambda: vistos.append(correlation_id_atual()))

    assert id_de_correlacao_valido(vistos[0])
    inicio, fim = _registros(caplog)
    assert inicio.evento == "job_iniciado"
    assert fim.evento == "job_concluido"
    assert fim.job == "ciclo_cripto"
    assert fim.duracao_ms >= 0
    assert inicio.correlation_id == fim.correlation_id == vistos[0]


def test_cada_execucao_tem_um_id_diferente():
    vistos = []

    executar_job("a", lambda: vistos.append(correlation_id_atual()))
    executar_job("a", lambda: vistos.append(correlation_id_atual()))

    assert vistos[0] != vistos[1]
    assert correlation_id_atual() is None


def test_falha_no_job_e_logada_como_erro_sem_propagar(caplog):
    def explodir():
        raise RuntimeError("quebrou")

    caplog.set_level(logging.INFO)

    executar_job("indices_referencia", explodir)

    falha = _registros(caplog)[-1]
    assert falha.evento == "job_falhou"
    assert falha.levelno == logging.ERROR
    assert falha.exc_info is not None
