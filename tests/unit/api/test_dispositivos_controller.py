_TOKEN = "ExponentPushToken[abc123]"


def test_registrar_sem_autenticacao_retorna_401(client):
    resposta = client.post("/api/v1/dispositivos", json={"token": _TOKEN})

    assert resposta.status_code == 401


def test_registrar_token_novo_retorna_201(client, auth_headers, dispositivo_push_repository):
    resposta = client.post("/api/v1/dispositivos", json={"token": _TOKEN}, headers=auth_headers)

    assert resposta.status_code == 201
    assert resposta.json() == {"token": _TOKEN, "ativo": True}
    assert len(dispositivo_push_repository.listar_todos()) == 1


def test_registrar_o_mesmo_token_de_novo_retorna_200(client, auth_headers):
    client.post("/api/v1/dispositivos", json={"token": _TOKEN}, headers=auth_headers)

    resposta = client.post("/api/v1/dispositivos", json={"token": _TOKEN}, headers=auth_headers)

    assert resposta.status_code == 200
    assert resposta.json() == {"token": _TOKEN, "ativo": True}


def test_registrar_token_de_outra_conta_transfere(
    client, auth_headers, auth_headers_outro_usuario, dispositivo_push_repository
):
    client.post("/api/v1/dispositivos", json={"token": _TOKEN}, headers=auth_headers)

    primeiro_dono = dispositivo_push_repository.listar_todos()[0].usuario_id

    resposta = client.post(
        "/api/v1/dispositivos", json={"token": _TOKEN}, headers=auth_headers_outro_usuario
    )

    assert resposta.status_code == 200
    (dispositivo,) = dispositivo_push_repository.listar_todos()
    assert dispositivo.usuario_id != primeiro_dono
    assert dispositivo.ativo is True


def test_registrar_formato_invalido_retorna_422(client, auth_headers):
    resposta = client.post("/api/v1/dispositivos", json={"token": "abc"}, headers=auth_headers)

    assert resposta.status_code == 422
    assert resposta.json() == {"detail": "Token de push invalido"}


def test_registrar_token_longo_demais_retorna_422(client, auth_headers):
    token = "ExponentPushToken[" + "a" * 300 + "]"

    resposta = client.post("/api/v1/dispositivos", json={"token": token}, headers=auth_headers)

    assert resposta.status_code == 422


def test_remover_retorna_204_e_desativa(client, auth_headers, dispositivo_push_repository):
    client.post("/api/v1/dispositivos", json={"token": _TOKEN}, headers=auth_headers)

    resposta = client.delete("/api/v1/dispositivos", params={"token": _TOKEN}, headers=auth_headers)

    assert resposta.status_code == 204
    assert dispositivo_push_repository.listar_todos()[0].ativo is False


def test_remover_token_desconhecido_retorna_204(client, auth_headers):
    resposta = client.delete("/api/v1/dispositivos", params={"token": _TOKEN}, headers=auth_headers)

    assert resposta.status_code == 204


def test_remover_sem_token_na_query_retorna_422(client, auth_headers, dispositivo_push_repository):
    client.post("/api/v1/dispositivos", json={"token": _TOKEN}, headers=auth_headers)

    resposta = client.delete("/api/v1/dispositivos", headers=auth_headers)

    assert resposta.status_code == 422
    assert dispositivo_push_repository.listar_todos()[0].ativo is True


def test_remover_sem_autenticacao_retorna_401(client):
    resposta = client.delete("/api/v1/dispositivos", params={"token": _TOKEN})

    assert resposta.status_code == 401
