from app.core.config import Settings
from app.integrations.expo.fabrica import criar_expo_client
from app.notifications.canais import montar_canais
from tests.fixtures.fake_barramento_notificacoes import FakeBarramentoNotificacoes
from tests.fixtures.fake_dispositivo_push_repository import FakeDispositivoPushRepository
from tests.fixtures.fake_ticket_push_repository import FakeTicketPushRepository


def _nomes(settings: Settings) -> list[str]:
    canais = montar_canais(
        settings,
        FakeBarramentoNotificacoes(),
        FakeDispositivoPushRepository(),
        FakeTicketPushRepository(),
        criar_expo_client(settings),
    )
    return [type(canal).__name__ for canal in canais]


def test_com_push_habilitado_monta_tempo_real_e_expo():
    assert _nomes(Settings(_env_file=None)) == ["CanalTempoReal", "CanalExpo"]


def test_com_push_desabilitado_monta_so_tempo_real():
    assert _nomes(Settings(_env_file=None, expo_push_habilitado=False)) == ["CanalTempoReal"]
