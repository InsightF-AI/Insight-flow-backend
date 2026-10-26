import json
import logging
import smtplib
from typing import ClassVar

import httpx

from app.integrations.email.enviador import Email, EnviadorBrevo, EnviadorLog, EnviadorSmtp

_EMAIL = Email("ana@example.com", "Assunto", "corpo com link secreto")


class _SmtpFalso:
    instancias: ClassVar[list] = []

    def __init__(self, host, porta, timeout):
        self.args = (host, porta, timeout)
        self.chamadas: list = []
        _SmtpFalso.instancias.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        self.chamadas.append("starttls")

    def login(self, usuario, senha):
        self.chamadas.append(("login", usuario, senha))

    def send_message(self, mensagem):
        self.chamadas.append(("send", mensagem["To"], mensagem["Subject"], mensagem["From"]))


def test_smtp_usa_starttls_login_e_envia():
    _SmtpFalso.instancias.clear()
    enviador = EnviadorSmtp(
        "smtp.test", 587, "user", "pass", "no-reply@test", fabrica_smtp=_SmtpFalso
    )

    enviador.enviar(_EMAIL)

    smtp = _SmtpFalso.instancias[0]
    assert smtp.args == ("smtp.test", 587, 10.0)
    assert smtp.chamadas == [
        "starttls",
        ("login", "user", "pass"),
        ("send", "ana@example.com", "Assunto", "no-reply@test"),
    ]


def test_falha_de_smtp_e_registrada_sem_estourar(caplog):
    def fabrica(*args, **kwargs):
        raise smtplib.SMTPConnectError(421, "fora")

    with caplog.at_level(logging.WARNING):
        EnviadorSmtp("smtp.test", 587, "", "", "x@test", fabrica_smtp=fabrica).enviar(_EMAIL)

    assert "Falha ao enviar e-mail" in caplog.text


def test_log_em_desenvolvimento_mostra_o_corpo(caplog):
    with caplog.at_level(logging.INFO):
        EnviadorLog(incluir_corpo=True).enviar(_EMAIL)

    assert "link secreto" in caplog.text


def test_log_em_producao_nao_vaza_o_corpo(caplog):
    with caplog.at_level(logging.INFO):
        EnviadorLog(incluir_corpo=False).enviar(_EMAIL)

    assert "link secreto" not in caplog.text
    assert "descartado" in caplog.text


def test_brevo_envia_pela_api_transacional():
    capturado = {}

    def handler(request: httpx.Request) -> httpx.Response:
        capturado["path"] = request.url.path
        capturado["chave"] = request.headers["api-key"]
        capturado["corpo"] = json.loads(request.content)
        return httpx.Response(201, json={"messageId": "<id@brevo>"})

    cliente = httpx.Client(base_url="https://brevo.test", transport=httpx.MockTransport(handler))

    EnviadorBrevo(cliente, "chave", "no-reply@test", "InsightFlow").enviar(_EMAIL)

    assert capturado["path"] == "/v3/smtp/email"
    assert capturado["chave"] == "chave"
    assert capturado["corpo"] == {
        "sender": {"name": "InsightFlow", "email": "no-reply@test"},
        "to": [{"email": "ana@example.com"}],
        "subject": "Assunto",
        "textContent": "corpo com link secreto",
    }


def test_falha_da_brevo_e_registrada_sem_estourar(caplog):
    cliente = httpx.Client(
        base_url="https://brevo.test", transport=httpx.MockTransport(lambda _: httpx.Response(401))
    )

    with caplog.at_level(logging.WARNING):
        EnviadorBrevo(cliente, "errada", "no-reply@test", "InsightFlow").enviar(_EMAIL)

    assert "Falha ao enviar e-mail" in caplog.text
