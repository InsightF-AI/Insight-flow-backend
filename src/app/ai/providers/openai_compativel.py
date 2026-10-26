from __future__ import annotations

import json

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


class OpenAICompativelProvider(ProvedorLLM):
    def __init__(self, http_client: httpx.Client, nome: str, modelo: str, api_key: str = ""):
        self._http_client = http_client
        self.nome = nome
        self.modelo = modelo
        self._api_key = api_key

    def gerar_texto(self, system: str, prompt: str) -> str:
        resposta = self.conversar(
            system, [MensagemChat(papel=PapelMensagem.USUARIO, texto=prompt)], []
        )
        if not resposta.texto:
            raise LLMIndisponivelError(f"{self.nome} nao retornou texto")
        return resposta.texto

    def conversar(
        self,
        system: str,
        mensagens: list[MensagemChat],
        ferramentas: list[DeclaracaoFerramenta],
    ) -> RespostaLLM:
        payload: dict = {
            "model": self.modelo,
            "messages": [{"role": "system", "content": system}]
            + [item for mensagem in mensagens for item in self._converter_mensagem(mensagem)],
        }
        if ferramentas:
            payload["tools"] = [self._converter_ferramenta(f) for f in ferramentas]
        return self._interpretar(self._enviar(payload))

    @staticmethod
    def _converter_mensagem(mensagem: MensagemChat) -> list[dict]:
        if mensagem.papel == PapelMensagem.ASSISTENTE:
            item: dict = {"role": "assistant", "content": mensagem.texto or None}
            if mensagem.chamadas:
                item["tool_calls"] = [
                    {
                        "id": chamada.id,
                        "type": "function",
                        "function": {
                            "name": chamada.nome,
                            "arguments": json.dumps(chamada.argumentos, ensure_ascii=False),
                        },
                    }
                    for chamada in mensagem.chamadas
                ]
            return [item]

        itens = [
            {
                "role": "tool",
                "tool_call_id": resultado.id,
                "content": json.dumps(resultado.conteudo, ensure_ascii=False),
            }
            for resultado in mensagem.resultados
        ]
        if mensagem.texto:
            itens.append({"role": "user", "content": mensagem.texto})
        return itens

    @staticmethod
    def _converter_ferramenta(ferramenta: DeclaracaoFerramenta) -> dict:
        funcao: dict = {"name": ferramenta.nome, "description": ferramenta.descricao}
        if ferramenta.parametros is not None:
            funcao["parameters"] = ferramenta.parametros
        return {"type": "function", "function": funcao}

    def _enviar(self, payload: dict) -> dict:
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        try:
            resposta = self._http_client.post("/v1/chat/completions", json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise LLMIndisponivelError(str(exc)) from exc

        if resposta.status_code == 429:
            valor = resposta.headers.get("Retry-After")
            raise LLMCotaExcedidaError(int(valor) if valor and valor.isdigit() else None)
        if resposta.status_code >= 400:
            raise LLMIndisponivelError(f"{self.nome} respondeu {resposta.status_code}")
        try:
            return resposta.json()
        except ValueError as exc:
            raise LLMIndisponivelError(f"{self.nome} retornou corpo invalido") from exc

    def _interpretar(self, corpo: dict) -> RespostaLLM:
        escolhas = corpo.get("choices") or []
        if not escolhas:
            raise LLMIndisponivelError(f"{self.nome} nao retornou escolhas")

        mensagem = escolhas[0].get("message") or {}
        texto = mensagem.get("content") or ""
        try:
            chamadas = tuple(
                ChamadaFerramenta(
                    nome=chamada["function"]["name"],
                    argumentos=json.loads(chamada["function"].get("arguments") or "{}"),
                    id=chamada.get("id"),
                )
                for chamada in mensagem.get("tool_calls") or []
            )
        except (KeyError, ValueError) as exc:
            raise LLMIndisponivelError(f"{self.nome} retornou chamada invalida") from exc
        if not texto and not chamadas:
            raise LLMIndisponivelError(f"{self.nome} retornou resposta vazia")
        return RespostaLLM(texto=texto, chamadas=chamadas)
