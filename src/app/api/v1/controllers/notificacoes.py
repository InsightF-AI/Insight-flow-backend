from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_notificacao_service, get_usuario_atual
from app.api.v1.schemas.notificacao import NotificacaoResponse
from app.domain.entities.usuario import Usuario
from app.services.exceptions import NotificacaoNaoEncontradaError
from app.services.notificacao_service import NotificacaoService

router = APIRouter(prefix="/notificacoes", tags=["notificacoes"])


@router.get("", response_model=list[NotificacaoResponse])
def listar(
    apenas_nao_lidas: bool = False,
    usuario: Usuario = Depends(get_usuario_atual),
    service: NotificacaoService = Depends(get_notificacao_service),
) -> list[NotificacaoResponse]:
    notificacoes = service.listar_notificacoes(usuario.id, apenas_nao_lidas)
    return [NotificacaoResponse.de(notificacao) for notificacao in notificacoes]


@router.patch("/{notificacao_id}/lida", response_model=NotificacaoResponse)
def marcar_como_lida(
    notificacao_id: UUID,
    usuario: Usuario = Depends(get_usuario_atual),
    service: NotificacaoService = Depends(get_notificacao_service),
) -> NotificacaoResponse:
    try:
        notificacao = service.marcar_como_lida(usuario.id, notificacao_id)
    except NotificacaoNaoEncontradaError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notificacao nao encontrada") from exc

    return NotificacaoResponse.de(notificacao)
