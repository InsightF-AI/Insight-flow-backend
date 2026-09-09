from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_usuario_atual, get_watchlist_service
from app.api.v1.schemas.watchlist import (
    AdicionarWatchlistRequest,
    AtualizarNotificacaoRequest,
    ItemWatchlistResponse,
)
from app.domain.entities.usuario import Usuario
from app.integrations.brapi.client import BrapiIndisponivelError
from app.services.exceptions import (
    AtivoJaNaWatchlistError,
    AtivoNaoEncontradoError,
    ItemWatchlistNaoEncontradoError,
)
from app.services.watchlist_service import WatchlistService

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ItemWatchlistResponse)
def adicionar(
    dados: AdicionarWatchlistRequest,
    usuario: Usuario = Depends(get_usuario_atual),
    service: WatchlistService = Depends(get_watchlist_service),
) -> ItemWatchlistResponse:
    try:
        item = service.adicionar(usuario_id=usuario.id, ticker=dados.ticker)
    except AtivoJaNaWatchlistError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ativo ja esta na watchlist") from exc
    except AtivoNaoEncontradoError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ativo nao encontrado") from exc
    except BrapiIndisponivelError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Fonte de dados de mercado indisponivel"
        ) from exc

    return ItemWatchlistResponse.de(item)


@router.get("", response_model=list[ItemWatchlistResponse])
def listar(
    usuario: Usuario = Depends(get_usuario_atual),
    service: WatchlistService = Depends(get_watchlist_service),
) -> list[ItemWatchlistResponse]:
    itens = service.listar(usuario.id)
    return [ItemWatchlistResponse.de(item) for item in itens]


@router.delete("/{ativo_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover(
    ativo_id: UUID,
    usuario: Usuario = Depends(get_usuario_atual),
    service: WatchlistService = Depends(get_watchlist_service),
) -> None:
    try:
        service.remover(usuario.id, ativo_id)
    except ItemWatchlistNaoEncontradoError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item nao encontrado na watchlist") from exc


@router.patch("/{ativo_id}/notificacao", response_model=ItemWatchlistResponse)
def atualizar_notificacao(
    ativo_id: UUID,
    dados: AtualizarNotificacaoRequest,
    usuario: Usuario = Depends(get_usuario_atual),
    service: WatchlistService = Depends(get_watchlist_service),
) -> ItemWatchlistResponse:
    try:
        item = service.definir_notificacao(usuario.id, ativo_id, dados.notificar)
    except ItemWatchlistNaoEncontradoError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item nao encontrado na watchlist") from exc

    return ItemWatchlistResponse.de(item)
