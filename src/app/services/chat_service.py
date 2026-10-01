from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.ai.ferramentas_chat import ExecutorFerramentas
from app.ai.guardrails.aplicar import gerar_com_guardrail
from app.ai.prompts.chat import SYSTEM_PROMPT_CHAT
from app.ai.providers.base import MensagemChat, PapelMensagem, ProvedorLLM
from app.services.exceptions import LLMIndisponivelError


@dataclass
class RespostaChat:
    texto: str
    modelo: str


class ChatService:
    def __init__(
        self,
        provedor: ProvedorLLM,
        executor: ExecutorFerramentas,
        max_iteracoes: int,
    ):
        self._provedor = provedor
        self._executor = executor
        self._max_iteracoes = max_iteracoes

    def responder(self, usuario_id: UUID, mensagens: list[MensagemChat]) -> RespostaChat:
        texto = gerar_com_guardrail(
            lambda system: self._executar_loop(usuario_id, system, mensagens),
            SYSTEM_PROMPT_CHAT,
        )
        return RespostaChat(texto=texto, modelo=self._provedor.modelo)

    def _executar_loop(self, usuario_id: UUID, system: str, mensagens: list[MensagemChat]) -> str:
        historico = list(mensagens)
        ferramentas = self._executor.declaracoes()
        for _ in range(self._max_iteracoes + 1):
            resposta = self._provedor.conversar(system, historico, ferramentas)
            if not resposta.chamadas:
                return resposta.texto
            historico.append(
                MensagemChat(papel=PapelMensagem.ASSISTENTE, chamadas=resposta.chamadas)
            )
            resultados = tuple(
                self._executor.executar(usuario_id, chamada) for chamada in resposta.chamadas
            )
            historico.append(MensagemChat(papel=PapelMensagem.USUARIO, resultados=resultados))
        raise LLMIndisponivelError("Limite de iteracoes de ferramentas excedido")
