def test_cadastrar_usuario_retorna_201_e_token_de_acesso(client):
    resposta = client.post(
        "/api/v1/usuarios",
        json={"nome": "Ana", "email": "ana@example.com", "senha": "segredo123"},
    )

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["token_type"] == "bearer"
    assert corpo["access_token"]


def test_cadastrar_usuario_com_email_ja_cadastrado_retorna_409(client):
    client.post(
        "/api/v1/usuarios",
        json={"nome": "Ana", "email": "ana@example.com", "senha": "segredo123"},
    )

    resposta = client.post(
        "/api/v1/usuarios",
        json={"nome": "Outra Ana", "email": "ana@example.com", "senha": "outrasenha"},
    )

    assert resposta.status_code == 409


def test_cadastrar_usuario_com_email_invalido_retorna_422(client):
    resposta = client.post(
        "/api/v1/usuarios",
        json={"nome": "Ana", "email": "nao-e-um-email", "senha": "segredo123"},
    )

    assert resposta.status_code == 422


def test_cadastrar_usuario_com_senha_curta_retorna_422(client):
    resposta = client.post(
        "/api/v1/usuarios",
        json={"nome": "Ana", "email": "ana@example.com", "senha": "curta"},
    )

    assert resposta.status_code == 422
