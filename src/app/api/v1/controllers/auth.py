from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_usuario_service
from app.api.v1.schemas.auth import LoginRequest
from app.api.v1.schemas.token import TokenResponse
from app.core.config import Settings, get_settings
from app.core.security import criar_token
from app.services.exceptions import CredenciaisInvalidasError
from app.services.usuario_service import UsuarioService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(
    dados: LoginRequest,
    service: UsuarioService = Depends(get_usuario_service),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    try:
        usuario = service.autenticar(email=dados.email, senha=dados.senha)
    except CredenciaisInvalidasError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciais inválidas") from exc

    token = criar_token(usuario.id, settings.jwt_secret_key, settings.jwt_expiration_minutes)
    return TokenResponse(access_token=token)
