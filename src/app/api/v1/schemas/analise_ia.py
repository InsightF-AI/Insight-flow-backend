from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.ai.guardrails.aviso_legal import AVISO_LEGAL
from app.ai.providers.base import MensagemChat, PapelMensagem
from app.services.analise_ia_service import ResultadoAnalise
from app.services.chat_service import RespostaChat


class AnaliseIAResponse(BaseModel):
    ativo_id: UUID
    texto: str
    gerado_em: datetime
    modelo: str
    em_cache: bool
    aviso_legal: str

    @staticmethod
    def de(resultado: ResultadoAnalise) -> "AnaliseIAResponse":
        return AnaliseIAResponse(
            ativo_id=resultado.analise.ativo_id,
            texto=resultado.analise.texto,
            gerado_em=resultado.analise.gerado_em,
            modelo=resultado.analise.modelo,
            em_cache=resultado.em_cache,
            aviso_legal=AVISO_LEGAL,
        )


class MensagemChatRequest(BaseModel):
    papel: Literal["usuario", "assistente"]
    texto: str

    def para_dominio(self) -> MensagemChat:
        return MensagemChat(papel=PapelMensagem(self.papel), texto=self.texto)


class ChatRequest(BaseModel):
    mensagens: list[MensagemChatRequest]


class ChatResponse(BaseModel):
    texto: str
    modelo: str
    aviso_legal: str

    @staticmethod
    def de(resposta: RespostaChat) -> "ChatResponse":
        return ChatResponse(texto=resposta.texto, modelo=resposta.modelo, aviso_legal=AVISO_LEGAL)
