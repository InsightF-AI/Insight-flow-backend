from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_analise_ia_service, get_chat_service, get_usuario_atual
from app.api.v1.schemas.analise_ia import (
    AnaliseIAResponse,
    ChatRequest,
    ChatResponse,
)
from app.core.config import Settings, get_settings
from app.domain.entities.usuario import Usuario
from app.services.analise_ia_service import AnaliseIAService
from app.services.chat_service import ChatService
from app.services.exceptions import (
    AtivoNaoEncontradoError,
    ContextoInsuficienteError,
    LLMCotaExcedidaError,
    LLMIndisponivelError,
    RespostaViolaGuardrailError,
)

router = APIRouter(tags=["analise-ia"])


def _erro_cota(exc: LLMCotaExcedidaError) -> HTTPException:
    headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after is not None else None
    return HTTPException(
        status.HTTP_503_SERVICE_UNAVAILABLE, "Cota do provedor de IA excedida", headers=headers
    )


@router.get("/ativos/{ativo_id}/analise", response_model=AnaliseIAResponse)
def analisar_ativo(
    ativo_id: UUID,
    usuario: Usuario = Depends(get_usuario_atual),
    service: AnaliseIAService = Depends(get_analise_ia_service),
) -> AnaliseIAResponse:
    try:
        resultado = service.analisar_ativo(ativo_id)
    except AtivoNaoEncontradoError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ativo nao encontrado") from exc
    except ContextoInsuficienteError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Dados insuficientes para gerar a analise"
        ) from exc
    except LLMCotaExcedidaError as exc:
        raise _erro_cota(exc) from exc
    except LLMIndisponivelError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Provedor de IA indisponivel"
        ) from exc
    except RespostaViolaGuardrailError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "Resposta da IA bloqueada pelo guardrail"
        ) from exc

    return AnaliseIAResponse.de(resultado)


@router.post("/chat", response_model=ChatResponse)
def conversar(
    dados: ChatRequest,
    usuario: Usuario = Depends(get_usuario_atual),
    service: ChatService = Depends(get_chat_service),
    settings: Settings = Depends(get_settings),
) -> ChatResponse:
    _validar_chat(dados, settings)
    mensagens = [mensagem.para_dominio() for mensagem in dados.mensagens]
    try:
        resposta = service.responder(usuario.id, mensagens)
    except LLMCotaExcedidaError as exc:
        raise _erro_cota(exc) from exc
    except LLMIndisponivelError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Provedor de IA indisponivel"
        ) from exc
    except RespostaViolaGuardrailError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "Resposta da IA bloqueada pelo guardrail"
        ) from exc

    return ChatResponse.de(resposta)


def _validar_chat(dados: ChatRequest, settings: Settings) -> None:
    mensagens = dados.mensagens
    if not mensagens:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Envie ao menos uma mensagem")
    if len(mensagens) > settings.chat_max_mensagens:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Limite de {settings.chat_max_mensagens} mensagens excedido",
        )
    if mensagens[-1].papel != "usuario":
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "A ultima mensagem deve ser do usuario"
        )
    for mensagem in mensagens:
        if not mensagem.texto.strip():
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Mensagem vazia")
        if len(mensagem.texto) > settings.chat_max_caracteres_mensagem:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Mensagem excede {settings.chat_max_caracteres_mensagem} caracteres",
            )
