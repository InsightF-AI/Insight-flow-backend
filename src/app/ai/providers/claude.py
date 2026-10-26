from __future__ import annotations

import json

import anthropic

from app.ai.providers.base import (
    ChamadaFerramenta,
    DeclaracaoFerramenta,
    MensagemChat,
    PapelMensagem,
    ProvedorLLM,
    RespostaLLM,
)
from app.services.exceptions import LLMCotaExcedidaError, LLMIndisponivelError

_MAX_TOKENS = 16000
_ESQUEMA_VAZIO = {"type": "object", "properties": {}}


class ClaudeProvider(ProvedorLLM):
    nome = "claude"

    def __init__(self, cliente: anthropic.Anthropic, modelo: str, esforco: str):
        self._cliente = cliente
        self.modelo = modelo
        self._esforco = esforco

    def gerar_texto(self, system: str, prompt: str) -> str:
        resposta = self.conversar(
            system, [MensagemChat(papel=PapelMensagem.USUARIO, texto=prompt)], []
        )
        if not resposta.texto:
            raise LLMIndisponivelError("Claude nao retornou texto")
        return resposta.texto

    def conversar(
        self,
        system: str,
        mensagens: list[MensagemChat],
        ferramentas: list[DeclaracaoFerramenta],
    ) -> RespostaLLM:
        parametros: dict = {
            "model": self.modelo,
            "max_tokens": _MAX_TOKENS,
            "system": system,
            "messages": [self._converter_mensagem(mensagem) for mensagem in mensagens],
            "output_config": {"effort": self._esforco},
        }
        if ferramentas:
            parametros["tools"] = [self._converter_ferramenta(f) for f in ferramentas]

        try:
            resposta = self._cliente.messages.create(**parametros)
        except anthropic.RateLimitError as exc:
            raise LLMCotaExcedidaError(_ler_retry_after(exc.response)) from exc
        except (anthropic.APIStatusError, anthropic.APIConnectionError) as exc:
            raise LLMIndisponivelError(f"Claude falhou: {exc}") from exc

        return self._interpretar(resposta)

    @staticmethod
    def _converter_mensagem(mensagem: MensagemChat) -> dict:
        if mensagem.papel == PapelMensagem.ASSISTENTE:
            if mensagem.estado is not None:
                return {"role": "assistant", "content": mensagem.estado}
            blocos: list[dict] = []
            if mensagem.texto:
                blocos.append({"type": "text", "text": mensagem.texto})
            for chamada in mensagem.chamadas:
                blocos.append(
                    {
                        "type": "tool_use",
                        "id": chamada.id,
                        "name": chamada.nome,
                        "input": chamada.argumentos,
                    }
                )
            return {"role": "assistant", "content": blocos}

        blocos = [
            {
                "type": "tool_result",
                "tool_use_id": resultado.id,
                "content": json.dumps(resultado.conteudo, ensure_ascii=False),
            }
            for resultado in mensagem.resultados
        ]
        if mensagem.texto:
            blocos.append({"type": "text", "text": mensagem.texto})
        return {"role": "user", "content": blocos}

    @staticmethod
    def _converter_ferramenta(ferramenta: DeclaracaoFerramenta) -> dict:
        return {
            "name": ferramenta.nome,
            "description": ferramenta.descricao,
            "input_schema": ferramenta.parametros or _ESQUEMA_VAZIO,
        }

    @staticmethod
    def _interpretar(resposta) -> RespostaLLM:
        if resposta.stop_reason == "refusal":
            raise LLMIndisponivelError("Claude recusou a solicitacao")

        texto = "".join(bloco.text for bloco in resposta.content if bloco.type == "text")
        chamadas = tuple(
            ChamadaFerramenta(nome=bloco.name, argumentos=dict(bloco.input or {}), id=bloco.id)
            for bloco in resposta.content
            if bloco.type == "tool_use"
        )
        if not texto and not chamadas:
            raise LLMIndisponivelError(f"Claude retornou resposta vazia ({resposta.stop_reason})")
        return RespostaLLM(texto=texto, chamadas=chamadas, estado=list(resposta.content))


def _ler_retry_after(resposta) -> int | None:
    valor = resposta.headers.get("retry-after") if resposta is not None else None
    if valor is not None and valor.isdigit():
        return int(valor)
    return None
