from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import Settings
from app.scheduler.jobs import registrar_jobs


def _ids(settings: Settings) -> set[str]:
    scheduler = BackgroundScheduler()
    registrar_jobs(scheduler, settings)
    return {job.id for job in scheduler.get_jobs()}


def test_sem_ia_registra_apenas_os_ciclos_de_monitoramento():
    assert _ids(Settings(_env_file=None)) == {"ciclo_renda_variavel", "ciclo_cripto"}


def test_ia_habilitada_sem_chave_nao_registra_resumo():
    assert "resumo_diario" not in _ids(Settings(_env_file=None, ai_habilitada=True))


def test_provedor_diferente_de_gemini_nao_registra_resumo():
    settings = Settings(
        _env_file=None, ai_habilitada=True, gemini_api_key="chave", ai_provider="ollama"
    )

    assert "resumo_diario" not in _ids(settings)


def test_ia_habilitada_com_chave_registra_resumo_diario_no_horario_de_sao_paulo():
    settings = Settings(
        _env_file=None,
        ai_habilitada=True,
        gemini_api_key="chave",
        resumo_diario_hora=18,
        resumo_diario_minuto=30,
    )
    scheduler = BackgroundScheduler()

    registrar_jobs(scheduler, settings)

    job = next(j for j in scheduler.get_jobs() if j.id == "resumo_diario")
    assert str(job.trigger.timezone) == "America/Sao_Paulo"
    campos = {campo.name: str(campo) for campo in job.trigger.fields}
    assert campos["hour"] == "18"
    assert campos["minute"] == "30"
