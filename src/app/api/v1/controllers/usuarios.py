from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_usuario_service
from app.api.v1.schemas.token import TokenResponse
from app.api.v1.schemas.usuario import CadastroRequest
from app.core.config import Settings, get_settings
from app.core.security import criar_token
from app.services.exceptions import EmailJaCadastradoError
from app.services.usuario_service import UsuarioService

router = APIRouter(prefix="/usuarios", tags=["usuarios"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=TokenResponse)
def cadastrar(
    dados: CadastroRequest,
    service: UsuarioService = Depends(get_usuario_service),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    try:
        usuario = service.cadastrar(nome=dados.nome, email=dados.email, senha=dados.senha)
    except EmailJaCadastradoError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "E-mail já cadastrado") from exc

    token = criar_token(usuario.id, settings.jwt_secret_key, settings.jwt_expiration_minutes)
    return TokenResponse(access_token=token)
