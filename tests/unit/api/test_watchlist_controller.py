def test_adicionar_sem_token_retorna_401(client):
    resposta = client.post(
        "/api/v1/watchlist",
        json={"ticker": "PETR4", "nome": "Petrobras PN", "tipo": "ACAO", "moeda": "BRL"},
    )

    assert resposta.status_code == 401


def test_adicionar_com_token_retorna_201_e_o_item_criado(client, auth_headers):
    resposta = client.post(
        "/api/v1/watchlist",
        json={"ticker": "PETR4", "nome": "Petrobras PN", "tipo": "ACAO", "moeda": "BRL"},
        headers=auth_headers,
    )

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["ativo"]["ticker"] == "PETR4"
    assert corpo["notificar"] is True


def test_adicionar_ativo_repetido_retorna_409(client, auth_headers):
    client.post(
        "/api/v1/watchlist",
        json={"ticker": "PETR4", "nome": "Petrobras PN", "tipo": "ACAO", "moeda": "BRL"},
        headers=auth_headers,
    )

    resposta = client.post(
        "/api/v1/watchlist",
        json={"ticker": "PETR4", "nome": "Petrobras PN", "tipo": "ACAO", "moeda": "BRL"},
        headers=auth_headers,
    )

    assert resposta.status_code == 409


def test_listar_retorna_os_itens_do_usuario_autenticado(client, auth_headers):
    client.post(
        "/api/v1/watchlist",
        json={"ticker": "PETR4", "nome": "Petrobras PN", "tipo": "ACAO", "moeda": "BRL"},
        headers=auth_headers,
    )

    resposta = client.get("/api/v1/watchlist", headers=auth_headers)

    assert resposta.status_code == 200
    itens = resposta.json()
    assert len(itens) == 1
    assert itens[0]["ativo"]["ticker"] == "PETR4"


def test_remover_item_existente_retorna_204(client, auth_headers):
    criado = client.post(
        "/api/v1/watchlist",
        json={"ticker": "PETR4", "nome": "Petrobras PN", "tipo": "ACAO", "moeda": "BRL"},
        headers=auth_headers,
    )
    ativo_id = criado.json()["ativo"]["id"]

    resposta = client.delete(f"/api/v1/watchlist/{ativo_id}", headers=auth_headers)

    assert resposta.status_code == 204
    assert client.get("/api/v1/watchlist", headers=auth_headers).json() == []


def test_remover_item_inexistente_retorna_404(client, auth_headers):
    resposta = client.delete(
        "/api/v1/watchlist/00000000-0000-0000-0000-000000000000", headers=auth_headers
    )

    assert resposta.status_code == 404


def test_atualizar_notificacao_desabilita_para_o_item(client, auth_headers):
    criado = client.post(
        "/api/v1/watchlist",
        json={"ticker": "PETR4", "nome": "Petrobras PN", "tipo": "ACAO", "moeda": "BRL"},
        headers=auth_headers,
    )
    ativo_id = criado.json()["ativo"]["id"]

    resposta = client.patch(
        f"/api/v1/watchlist/{ativo_id}/notificacao",
        json={"notificar": False},
        headers=auth_headers,
    )

    assert resposta.status_code == 200
    assert resposta.json()["notificar"] is False


def test_atualizar_notificacao_de_item_inexistente_retorna_404(client, auth_headers):
    resposta = client.patch(
        "/api/v1/watchlist/00000000-0000-0000-0000-000000000000/notificacao",
        json={"notificar": False},
        headers=auth_headers,
    )

    assert resposta.status_code == 404


def test_usuario_nao_remove_item_da_watchlist_de_outro_usuario(
    client, auth_headers, auth_headers_outro_usuario
):
    criado = client.post(
        "/api/v1/watchlist",
        json={"ticker": "PETR4", "nome": "Petrobras PN", "tipo": "ACAO", "moeda": "BRL"},
        headers=auth_headers,
    )
    ativo_id = criado.json()["ativo"]["id"]

    resposta = client.delete(f"/api/v1/watchlist/{ativo_id}", headers=auth_headers_outro_usuario)

    assert resposta.status_code == 404
    assert len(client.get("/api/v1/watchlist", headers=auth_headers).json()) == 1
