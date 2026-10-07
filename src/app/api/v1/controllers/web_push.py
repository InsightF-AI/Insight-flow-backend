from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps import get_inscricao_web_push_service, get_usuario_atual
from app.api.v1.schemas.web_push import (
    ChavePublicaResponse,
    InscricaoResponse,
    RegistrarInscricaoRequest,
)
from app.core.config import Settings, get_settings
from app.domain.entities.usuario import Usuario
from app.integrations.web_push.validacao import InscricaoWebPushInvalidaError
from app.integrations.web_push.vapid import ChaveVapid
from app.services.inscricao_web_push_service import InscricaoWebPushService

router = APIRouter(prefix="/web-push", tags=["web-push"])


@router.get("/chave-publica", response_model=ChavePublicaResponse)
def chave_publica(settings: Settings = Depends(get_settings)) -> ChavePublicaResponse:
    if not settings.web_push_configurado():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Web push nao configurado")
    chave = ChaveVapid.de_base64url(settings.web_push_vapid_chave_privada)
    return ChavePublicaResponse(chave_publica=chave.publica_base64url())


@router.post(
    "/inscricoes",
    response_model=InscricaoResponse,
    status_code=status.HTTP_201_CREATED,
    responses={200: {"model": InscricaoResponse}},
)
def registrar(
    dados: RegistrarInscricaoRequest,
    response: Response,
    usuario: Usuario = Depends(get_usuario_atual),
    service: InscricaoWebPushService = Depends(get_inscricao_web_push_service),
) -> InscricaoResponse:
    try:
        criada = service.registrar(usuario.id, dados.endpoint, dados.keys.p256dh, dados.keys.auth)
    except InscricaoWebPushInvalidaError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Inscricao de web push invalida"
        ) from exc

    if not criada:
        response.status_code = status.HTTP_200_OK
    return InscricaoResponse(endpoint=dados.endpoint)


@router.delete("/inscricoes", status_code=status.HTTP_204_NO_CONTENT)
def remover(
    endpoint: str,
    usuario: Usuario = Depends(get_usuario_atual),
    service: InscricaoWebPushService = Depends(get_inscricao_web_push_service),
) -> None:
    service.remover(usuario.id, endpoint)
