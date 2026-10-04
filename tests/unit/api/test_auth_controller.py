from app.core.config import get_settings


def test_login_com_credenciais_corretas_retorna_token(client):
    client.post(
        "/api/v1/usuarios",
        json={"nome": "Ana", "email": "ana@example.com", "senha": "segredo123"},
    )

    resposta = client.post(
        "/api/v1/auth/login",
        json={"email": "ana@example.com", "senha": "segredo123"},
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["token_type"] == "bearer"
    assert corpo["access_token"]


def test_login_com_senha_incorreta_retorna_401(client):
    client.post(
        "/api/v1/usuarios",
        json={"nome": "Ana", "email": "ana@example.com", "senha": "segredo123"},
    )

    resposta = client.post(
        "/api/v1/auth/login",
        json={"email": "ana@example.com", "senha": "senhaerrada"},
    )

    assert resposta.status_code == 401


def test_login_com_email_inexistente_retorna_401(client):
    resposta = client.post(
        "/api/v1/auth/login",
        json={"email": "naoexiste@example.com", "senha": "qualquer123"},
    )

    assert resposta.status_code == 401


def _cadastrar(client) -> dict:
    resposta = client.post(
        "/api/v1/usuarios",
        json={"nome": "Ana", "email": "ana@example.com", "senha": "segredo123"},
    )
    return resposta.json()


def test_cadastro_e_login_devolvem_refresh_token_e_expires_in(client):
    cadastro = _cadastrar(client)
    login = client.post(
        "/api/v1/auth/login", json={"email": "ana@example.com", "senha": "segredo123"}
    ).json()

    for corpo in (cadastro, login):
        assert corpo["refresh_token"]
        assert corpo["expires_in"] == get_settings().jwt_expiration_minutes * 60
        assert corpo["token_type"] == "bearer"
    assert cadastro["refresh_token"] != login["refresh_token"]


def test_refresh_devolve_tokens_novos_que_autenticam(client):
    tokens = _cadastrar(client)

    resposta = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})

    assert resposta.status_code == 200
    novos = resposta.json()
    assert novos["refresh_token"] != tokens["refresh_token"]
    protegido = client.get(
        "/api/v1/watchlist", headers={"Authorization": f"Bearer {novos['access_token']}"}
    )
    assert protegido.status_code == 200


def test_reuso_do_refresh_antigo_retorna_401_e_derruba_o_novo(client):
    tokens = _cadastrar(client)
    novos = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    ).json()

    reuso = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    depois = client.post("/api/v1/auth/refresh", json={"refresh_token": novos["refresh_token"]})

    assert reuso.status_code == 401
    assert depois.status_code == 401


def test_refresh_com_token_desconhecido_retorna_401(client):
    resposta = client.post("/api/v1/auth/refresh", json={"refresh_token": "nao-existe"})

    assert resposta.status_code == 401


def test_refresh_sem_corpo_retorna_422(client):
    assert client.post("/api/v1/auth/refresh", json={}).status_code == 422


def test_logout_retorna_204_e_o_refresh_seguinte_falha(client):
    tokens = _cadastrar(client)

    logout = client.post("/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    depois = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})

    assert logout.status_code == 204
    assert depois.status_code == 401


def test_logout_com_token_desconhecido_retorna_204(client):
    resposta = client.post("/api/v1/auth/logout", json={"refresh_token": "nao-existe"})

    assert resposta.status_code == 204
