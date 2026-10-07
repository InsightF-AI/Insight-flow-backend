import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_refresh_token_service, get_usuario_service
from app.api.v1.schemas.auth import LoginRequest, RefreshRequest
from app.api.v1.schemas.token import TokenResponse
from app.services.exceptions import CredenciaisInvalidasError, RefreshTokenInvalidoError
from app.services.refresh_token_service import RefreshTokenService
from app.services.usuario_service import UsuarioService

router = APIRouter(prefix="/auth", tags=["auth"])

logger = logging.getLogger(__name__)


@router.post("/login", response_model=TokenResponse)
def login(
    dados: LoginRequest,
    service: UsuarioService = Depends(get_usuario_service),
    tokens: RefreshTokenService = Depends(get_refresh_token_service),
) -> TokenResponse:
    try:
        usuario = service.autenticar(email=dados.email, senha=dados.senha)
    except CredenciaisInvalidasError as exc:
        logger.warning("Login recusado.", extra={"evento": "login_recusado"})
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciais inválidas") from exc

    logger.info("Login aceito.", extra={"evento": "login_aceito", "usuario_id": str(usuario.id)})
    return TokenResponse.de(tokens.emitir(usuario.id))


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    dados: RefreshRequest,
    tokens: RefreshTokenService = Depends(get_refresh_token_service),
) -> TokenResponse:
    try:
        par = tokens.renovar(dados.refresh_token)
    except RefreshTokenInvalidoError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token invalido") from exc

    return TokenResponse.de(par)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    dados: RefreshRequest,
    tokens: RefreshTokenService = Depends(get_refresh_token_service),
) -> None:
    tokens.revogar(dados.refresh_token)
