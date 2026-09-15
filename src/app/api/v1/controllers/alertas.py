from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_alerta_service, get_usuario_atual
from app.api.v1.schemas.alerta import AlertaResponse, AtualizarAlertaRequest, CriarAlertaRequest
from app.domain.entities.usuario import Usuario
from app.integrations.brapi.client import BrapiIndisponivelError
from app.services.alerta_service import AlertaService
from app.services.exceptions import AlertaNaoEncontradoError, AtivoNaoEncontradoError

router = APIRouter(prefix="/alertas", tags=["alertas"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=AlertaResponse)
def criar(
    dados: CriarAlertaRequest,
    usuario: Usuario = Depends(get_usuario_atual),
    service: AlertaService = Depends(get_alerta_service),
) -> AlertaResponse:
    try:
        item = service.criar_alerta(
            usuario_id=usuario.id,
            ticker=dados.ticker,
            tipo_condicao=dados.tipo_condicao,
            valor_alvo=dados.valor_alvo,
        )
    except AtivoNaoEncontradoError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ativo nao encontrado") from exc
    except BrapiIndisponivelError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Fonte de dados de mercado indisponivel"
        ) from exc

    return AlertaResponse.de(item)


@router.get("", response_model=list[AlertaResponse])
def listar(
    usuario: Usuario = Depends(get_usuario_atual),
    service: AlertaService = Depends(get_alerta_service),
) -> list[AlertaResponse]:
    itens = service.listar_alertas(usuario.id)
    return [AlertaResponse.de(item) for item in itens]


@router.patch("/{alerta_id}", response_model=AlertaResponse)
def atualizar(
    alerta_id: UUID,
    dados: AtualizarAlertaRequest,
    usuario: Usuario = Depends(get_usuario_atual),
    service: AlertaService = Depends(get_alerta_service),
) -> AlertaResponse:
    try:
        item = service.atualizar_alerta(
            usuario_id=usuario.id,
            alerta_id=alerta_id,
            tipo_condicao=dados.tipo_condicao,
            valor_alvo=dados.valor_alvo,
            ativo=dados.ativo,
        )
    except AlertaNaoEncontradoError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alerta nao encontrado") from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    return AlertaResponse.de(item)


@router.delete("/{alerta_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover(
    alerta_id: UUID,
    usuario: Usuario = Depends(get_usuario_atual),
    service: AlertaService = Depends(get_alerta_service),
) -> None:
    try:
        service.remover_alerta(usuario.id, alerta_id)
    except AlertaNaoEncontradoError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alerta nao encontrado") from exc
