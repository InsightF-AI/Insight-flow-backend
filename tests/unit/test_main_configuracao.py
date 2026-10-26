import pytest
from fastapi.testclient import TestClient

from app import main
from app.core.config import Settings


def test_aplicacao_nao_sobe_com_configuracao_insegura(monkeypatch):
    settings = Settings(_env_file=None, ambiente="producao", scheduler_habilitado=False)
    monkeypatch.setattr(main, "get_settings", lambda: settings)

    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"), TestClient(main.app):
        pass
