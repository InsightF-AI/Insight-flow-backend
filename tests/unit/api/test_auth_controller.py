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
