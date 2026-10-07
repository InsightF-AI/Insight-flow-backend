from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps import get_dispositivo_push_service, get_usuario_atual
from app.api.v1.schemas.dispositivo import DispositivoResponse, RegistrarDispositivoRequest
from app.domain.entities.usuario import Usuario
from app.services.dispositivo_push_service import DispositivoPushService
from app.services.exceptions import TokenPushInvalidoError

router = APIRouter(prefix="/dispositivos", tags=["dispositivos"])


@router.post(
    "",
    response_model=DispositivoResponse,
    status_code=status.HTTP_201_CREATED,
    responses={200: {"model": DispositivoResponse}},
)
def registrar(
    dados: RegistrarDispositivoRequest,
    response: Response,
    usuario: Usuario = Depends(get_usuario_atual),
    service: DispositivoPushService = Depends(get_dispositivo_push_service),
) -> DispositivoResponse:
    try:
        criado = service.registrar(usuario.id, dados.token)
    except TokenPushInvalidoError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Token de push invalido") from exc

    if not criado:
        response.status_code = status.HTTP_200_OK
    return DispositivoResponse(token=dados.token.strip(), ativo=True)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def remover(
    token: str,
    usuario: Usuario = Depends(get_usuario_atual),
    service: DispositivoPushService = Depends(get_dispositivo_push_service),
) -> None:
    service.remover(usuario.id, token)
