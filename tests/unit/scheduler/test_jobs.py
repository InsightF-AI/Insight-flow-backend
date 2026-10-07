from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import Settings
from app.scheduler.jobs import _dados_mercado_service, _notificacao_service, registrar_jobs
from app.services.cached_dados_mercado_service import CachedDadosMercadoService
from app.services.roteador_dados_mercado_service import RoteadorDadosMercadoService
from tests.fixtures.fake_dispositivo_push_repository import FakeDispositivoPushRepository
from tests.fixtures.fake_inscricao_web_push_repository import FakeInscricaoWebPushRepository
from tests.fixtures.fake_mercado_cache import FakeMercadoCache
from tests.fixtures.fake_notificacao_repository import FakeNotificacaoRepository
from tests.fixtures.fake_ticket_push_repository import FakeTicketPushRepository


def _ids(settings: Settings) -> set[str]:
    scheduler = BackgroundScheduler()
    registrar_jobs(scheduler, settings)
    return {job.id for job in scheduler.get_jobs()}


def test_sem_ia_registra_apenas_os_ciclos_de_monitoramento_e_os_indices():
    assert _ids(Settings(_env_file=None)) == {
        "ciclo_renda_variavel",
        "ciclo_cripto",
        "indices_referencia",
        "recibos_push",
    }


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


def test_registra_atualizacao_dos_indices_no_horario_de_sao_paulo():
    settings = Settings(_env_file=None, indices_referencia_hora=19, indices_referencia_minuto=15)
    scheduler = BackgroundScheduler()

    registrar_jobs(scheduler, settings)

    job = next(j for j in scheduler.get_jobs() if j.id == "indices_referencia")
    assert str(job.trigger.timezone) == "America/Sao_Paulo"
    campos = {campo.name: str(campo) for campo in job.trigger.fields}
    assert campos["hour"] == "19"
    assert campos["minute"] == "15"


def test_dados_mercado_do_scheduler_envolve_o_roteador_no_cache():
    service = _dados_mercado_service(Settings(_env_file=None), FakeMercadoCache())

    assert isinstance(service, CachedDadosMercadoService)
    assert isinstance(service._interno, RoteadorDadosMercadoService)


def test_notificacao_service_do_scheduler_tem_os_canais_tempo_real_e_expo():
    service = _notificacao_service(
        Settings(_env_file=None),
        FakeNotificacaoRepository(),
        FakeDispositivoPushRepository(),
        FakeTicketPushRepository(),
        FakeInscricaoWebPushRepository(),
    )

    assert [type(canal).__name__ for canal in service._canais] == ["CanalTempoReal", "CanalExpo"]


def test_registra_job_de_recibos_push_quando_habilitado():
    assert "recibos_push" in _ids(Settings(_env_file=None))


def test_nao_registra_job_de_recibos_push_quando_desabilitado():
    assert "recibos_push" not in _ids(Settings(_env_file=None, expo_push_habilitado=False))


def test_job_de_recibos_push_usa_o_intervalo_configurado():
    scheduler = BackgroundScheduler()

    registrar_jobs(scheduler, Settings(_env_file=None, expo_recibos_intervalo_minutos=45))

    job = next(j for j in scheduler.get_jobs() if j.id == "recibos_push")
    assert job.trigger.interval.total_seconds() == 45 * 60
