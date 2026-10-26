from __future__ import annotations

import logging
import smtplib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from email.message import EmailMessage

import httpx

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Email:
    destinatario: str
    assunto: str
    corpo: str


class EnviadorEmail(ABC):
    @abstractmethod
    def enviar(self, email: Email) -> None: ...


class EnviadorSmtp(EnviadorEmail):
    def __init__(
        self,
        host: str,
        porta: int,
        usuario: str,
        senha: str,
        remetente: str,
        starttls: bool = True,
        timeout_segundos: float = 10.0,
        fabrica_smtp=smtplib.SMTP,
    ):
        self._host = host
        self._porta = porta
        self._usuario = usuario
        self._senha = senha
        self._remetente = remetente
        self._starttls = starttls
        self._timeout_segundos = timeout_segundos
        self._fabrica_smtp = fabrica_smtp

    def enviar(self, email: Email) -> None:
        mensagem = EmailMessage()
        mensagem["From"] = self._remetente
        mensagem["To"] = email.destinatario
        mensagem["Subject"] = email.assunto
        mensagem.set_content(email.corpo)
        try:
            with self._fabrica_smtp(
                self._host, self._porta, timeout=self._timeout_segundos
            ) as smtp:
                if self._starttls:
                    smtp.starttls()
                if self._usuario:
                    smtp.login(self._usuario, self._senha)
                smtp.send_message(mensagem)
        except (smtplib.SMTPException, OSError):
            logger.warning(
                "Falha ao enviar e-mail.", exc_info=True, extra={"evento": "email_falhou"}
            )


class EnviadorBrevo(EnviadorEmail):
    def __init__(
        self, http_client: httpx.Client, api_key: str, remetente: str, nome_remetente: str
    ):
        self._http_client = http_client
        self._api_key = api_key
        self._remetente = remetente
        self._nome_remetente = nome_remetente

    def enviar(self, email: Email) -> None:
        payload = {
            "sender": {"name": self._nome_remetente, "email": self._remetente},
            "to": [{"email": email.destinatario}],
            "subject": email.assunto,
            "textContent": email.corpo,
        }
        try:
            resposta = self._http_client.post(
                "/v3/smtp/email", json=payload, headers={"api-key": self._api_key}
            )
            resposta.raise_for_status()
        except httpx.HTTPError:
            logger.warning(
                "Falha ao enviar e-mail.", exc_info=True, extra={"evento": "email_falhou"}
            )


class EnviadorLog(EnviadorEmail):
    def __init__(self, incluir_corpo: bool):
        self._incluir_corpo = incluir_corpo

    def enviar(self, email: Email) -> None:
        if self._incluir_corpo:
            logger.info(
                "SMTP nao configurado; e-mail apenas registrado no log.\n%s",
                email.corpo,
                extra={"evento": "email_simulado"},
            )
            return
        logger.warning(
            "SMTP nao configurado; e-mail descartado.", extra={"evento": "email_descartado"}
        )
