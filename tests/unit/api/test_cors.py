from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import app


def _preflight(origem: str):
    return TestClient(app).options(
        "/api/v1/auth/login",
        headers={
            "Origin": origem,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Authorization, Content-Type",
        },
    )


def test_preflight_de_origem_configurada_e_permitido():
    resposta = _preflight("http://localhost:5173")

    assert resposta.status_code == 200
    assert resposta.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_preflight_de_origem_fora_da_lista_nao_recebe_permissao():
    resposta = _preflight("https://site-malicioso.example")

    assert "access-control-allow-origin" not in resposta.headers


def test_origens_de_cors_padrao_sao_o_vite_local():
    assert Settings(_env_file=None).cors_origens == ["http://localhost:5173"]
