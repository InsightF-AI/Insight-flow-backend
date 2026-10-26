from app.api.deps import get_enviador_email
from app.integrations.email.enviador import EnviadorEmail
from app.main import app


class _EnviadorCapturador(EnviadorEmail):
    def __init__(self):
        self.enviados = []

    def enviar(self, email):
        self.enviados.append(email)


def _login(client, senha):
    return client.post("/api/v1/auth/login", json={"email": "ana@example.com", "senha": senha})


def test_alterar_senha_troca_e_invalida_refresh_tokens(client, auth_headers):
    refresh = _login(client, "segredo123").json()["refresh_token"]

    resposta = client.put(
        "/api/v1/usuarios/me/senha",
        json={"senha_atual": "segredo123", "nova_senha": "novasenha456"},
        headers=auth_headers,
    )

    assert resposta.status_code == 204
    assert _login(client, "novasenha456").status_code == 200
    assert _login(client, "segredo123").status_code == 401
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": refresh}).status_code == 401


def test_alterar_senha_com_senha_atual_errada_retorna_400(client, auth_headers):
    resposta = client.put(
        "/api/v1/usuarios/me/senha",
        json={"senha_atual": "errada", "nova_senha": "novasenha456"},
        headers=auth_headers,
    )

    assert resposta.status_code == 400


def test_alterar_senha_curta_retorna_422(client, auth_headers):
    resposta = client.put(
        "/api/v1/usuarios/me/senha",
        json={"senha_atual": "segredo123", "nova_senha": "curta"},
        headers=auth_headers,
    )

    assert resposta.status_code == 422


def test_alterar_senha_exige_autenticacao(client):
    resposta = client.put(
        "/api/v1/usuarios/me/senha", json={"senha_atual": "a", "nova_senha": "novasenha456"}
    )

    assert resposta.status_code == 401


def test_recuperar_e_redefinir_senha(client, auth_headers):
    enviador = _EnviadorCapturador()
    app.dependency_overrides[get_enviador_email] = lambda: enviador

    resposta = client.post("/api/v1/auth/recuperar-senha", json={"email": "ana@example.com"})
    token = enviador.enviados[0].corpo.split("token=", 1)[1].split()[0]
    redefinicao = client.post(
        "/api/v1/auth/redefinir-senha", json={"token": token, "nova_senha": "novasenha456"}
    )

    assert resposta.status_code == 202
    assert redefinicao.status_code == 204
    assert _login(client, "novasenha456").status_code == 200


def test_recuperar_email_desconhecido_responde_igual_sem_enviar(client):
    enviador = _EnviadorCapturador()
    app.dependency_overrides[get_enviador_email] = lambda: enviador

    resposta = client.post("/api/v1/auth/recuperar-senha", json={"email": "x@example.com"})

    assert resposta.status_code == 202
    assert enviador.enviados == []


def test_redefinir_com_token_invalido_retorna_400(client):
    resposta = client.post(
        "/api/v1/auth/redefinir-senha", json={"token": "lixo", "nova_senha": "novasenha456"}
    )

    assert resposta.status_code == 400
