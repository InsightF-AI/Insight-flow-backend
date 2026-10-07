from app.core.config import Settings
from app.integrations.expo.fabrica import criar_expo_client
from app.integrations.web_push.fabrica import criar_web_push_client
from app.integrations.web_push.vapid import ChaveVapid
from app.notifications.canais import montar_canais
from tests.fixtures.fake_barramento_notificacoes import FakeBarramentoNotificacoes
from tests.fixtures.fake_dispositivo_push_repository import FakeDispositivoPushRepository
from tests.fixtures.fake_inscricao_web_push_repository import FakeInscricaoWebPushRepository
from tests.fixtures.fake_ticket_push_repository import FakeTicketPushRepository

_COM_WEB_PUSH = {
    "web_push_vapid_chave_privada": ChaveVapid.gerar().privada_base64url(),
    "web_push_vapid_contato": "mailto:a@b.c",
}


def _nomes(settings: Settings) -> list[str]:
    canais = montar_canais(
        settings,
        FakeBarramentoNotificacoes(),
        FakeDispositivoPushRepository(),
        FakeTicketPushRepository(),
        criar_expo_client(settings),
        FakeInscricaoWebPushRepository(),
        criar_web_push_client(settings),
    )
    return [type(canal).__name__ for canal in canais]


def test_sem_vapid_monta_tempo_real_e_expo():
    assert _nomes(Settings(_env_file=None)) == ["CanalTempoReal", "CanalExpo"]


def test_com_vapid_monta_os_tres_canais():
    assert _nomes(Settings(_env_file=None, **_COM_WEB_PUSH)) == [
        "CanalTempoReal",
        "CanalExpo",
        "CanalWebPush",
    ]


def test_com_push_desabilitados_monta_so_tempo_real():
    settings = Settings(
        _env_file=None, expo_push_habilitado=False, web_push_habilitado=False, **_COM_WEB_PUSH
    )

    assert _nomes(settings) == ["CanalTempoReal"]
