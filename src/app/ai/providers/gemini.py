from __future__ import annotations

import math
import time
from collections.abc import Callable

import httpx

from app.ai.providers.base import (
    ChamadaFerramenta,
    DeclaracaoFerramenta,
    MensagemChat,
    PapelMensagem,
    ProvedorLLM,
    RespostaLLM,
)
from app.services.exceptions import LLMCotaExcedidaError, LLMIndisponivelError

_TEMPERATURA = 0.2
_TENTATIVAS = 2


class GeminiProvider(ProvedorLLM):
    nome = "gemini"

    def __init__(
        self,
        http_client: httpx.Client,
        api_key: str,
        modelo: str,
        backoff_segundos: float = 2.0,
        dormir: Callable[[float], None] = time.sleep,
    ):
        self._http_client = http_client
        self._api_key = api_key
        self.modelo = modelo
        self._backoff_segundos = backoff_segundos
        self._dormir = dormir

    def gerar_texto(self, system: str, prompt: str) -> str:
        resposta = self.conversar(
            system, [MensagemChat(papel=PapelMensagem.USUARIO, texto=prompt)], []
        )
        if not resposta.texto:
            raise LLMIndisponivelError("Gemini nao retornou texto")
        return resposta.texto

    def conversar(
        self,
        system: str,
        mensagens: list[MensagemChat],
        ferramentas: list[DeclaracaoFerramenta],
    ) -> RespostaLLM:
        payload = self._montar_payload(system, mensagens, ferramentas)
        return self._interpretar(self._enviar(payload))

    def _montar_payload(
        self,
        system: str,
        mensagens: list[MensagemChat],
        ferramentas: list[DeclaracaoFerramenta],
    ) -> dict:
        payload: dict = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [self._converter_mensagem(mensagem) for mensagem in mensagens],
            "generationConfig": {"temperature": _TEMPERATURA},
        }
        if ferramentas:
            payload["tools"] = [
                {
                    "functionDeclarations": [
                        self._converter_ferramenta(ferramenta) for ferramenta in ferramentas
                    ]
                }
            ]
        return payload

    @staticmethod
    def _converter_mensagem(mensagem: MensagemChat) -> dict:
        partes: list[dict] = []
        if mensagem.texto:
            partes.append({"text": mensagem.texto})
        for chamada in mensagem.chamadas:
            parte: dict = {"functionCall": {"name": chamada.nome, "args": chamada.argumentos}}
            if chamada.assinatura is not None:
                parte["thoughtSignature"] = chamada.assinatura
            partes.append(parte)
        for resultado in mensagem.resultados:
            partes.append(
                {"functionResponse": {"name": resultado.nome, "response": resultado.conteudo}}
            )
        papel = "model" if mensagem.papel == PapelMensagem.ASSISTENTE else "user"
        return {"role": papel, "parts": partes}

    @staticmethod
    def _converter_ferramenta(ferramenta: DeclaracaoFerramenta) -> dict:
        declaracao: dict = {"name": ferramenta.nome, "description": ferramenta.descricao}
        if ferramenta.parametros is not None:
            declaracao["parameters"] = ferramenta.parametros
        return declaracao

    def _enviar(self, payload: dict) -> dict:
        ultima_falha: Exception | None = None
        for tentativa in range(_TENTATIVAS):
            if tentativa > 0:
                self._dormir(self._backoff_segundos)
            try:
                resposta = self._http_client.post(
                    f"/v1beta/models/{self.modelo}:generateContent",
                    json=payload,
                    headers={"x-goog-api-key": self._api_key},
                )
            except httpx.HTTPError as exc:
                ultima_falha = LLMIndisponivelError(str(exc))
                continue

            if resposta.status_code == 429:
                ultima_falha = LLMCotaExcedidaError(_ler_retry_after(resposta))
                continue
            if resposta.status_code >= 500:
                ultima_falha = LLMIndisponivelError(f"Gemini respondeu {resposta.status_code}")
                continue
            if resposta.status_code >= 400:
                raise LLMIndisponivelError(f"Gemini respondeu {resposta.status_code}")

            try:
                return resposta.json()
            except ValueError as exc:
                raise LLMIndisponivelError("Gemini retornou corpo invalido") from exc

        raise ultima_falha

    @staticmethod
    def _interpretar(corpo: dict) -> RespostaLLM:
        candidatos = corpo.get("candidates") or []
        if not candidatos:
            raise LLMIndisponivelError("Gemini nao retornou candidatos")

        partes = (candidatos[0].get("content") or {}).get("parts") or []
        texto = "".join(parte["text"] for parte in partes if "text" in parte)
        chamadas = tuple(
            ChamadaFerramenta(
                nome=parte["functionCall"]["name"],
                argumentos=parte["functionCall"].get("args") or {},
                assinatura=parte.get("thoughtSignature"),
            )
            for parte in partes
            if "functionCall" in parte
        )
        if not texto and not chamadas:
            raise LLMIndisponivelError("Gemini retornou resposta vazia")
        return RespostaLLM(texto=texto, chamadas=chamadas)


def _ler_retry_after(resposta: httpx.Response) -> int | None:
    valor = resposta.headers.get("Retry-After")
    if valor is not None and valor.isdigit():
        return int(valor)
    return _ler_retry_delay_do_corpo(resposta)


def _ler_retry_delay_do_corpo(resposta: httpx.Response) -> int | None:
    try:
        corpo = resposta.json()
    except ValueError:
        return None

    erro = corpo.get("error") if isinstance(corpo, dict) else None
    detalhes = erro.get("details") if isinstance(erro, dict) else None
    if not isinstance(detalhes, list):
        return None

    for detalhe in detalhes:
        atraso = detalhe.get("retryDelay") if isinstance(detalhe, dict) else None
        if isinstance(atraso, str) and atraso.endswith("s"):
            try:
                return math.ceil(float(atraso[:-1]))
            except ValueError:
                return None
    return None
