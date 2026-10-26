import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from app.api.deps import (
    get_enviador_email,
    get_refresh_token_service,
    get_senha_service,
    get_usuario_service,
)
from app.api.v1.schemas.auth import (
    LoginRequest,
    RecuperarSenhaRequest,
    RedefinirSenhaRequest,
    RefreshRequest,
)
from app.api.v1.schemas.token import TokenResponse
from app.integrations.email.enviador import EnviadorEmail
from app.services.exceptions import (
    CredenciaisInvalidasError,
    RefreshTokenInvalidoError,
    TokenRedefinicaoInvalidoError,
)
from app.services.refresh_token_service import RefreshTokenService
from app.services.senha_service import SenhaService
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


@router.post("/recuperar-senha", status_code=status.HTTP_202_ACCEPTED)
def recuperar_senha(
    dados: RecuperarSenhaRequest,
    tarefas: BackgroundTasks,
    service: SenhaService = Depends(get_senha_service),
    enviador: EnviadorEmail = Depends(get_enviador_email),
) -> None:
    email = service.preparar_recuperacao(dados.email)
    if email is not None:
        tarefas.add_task(enviador.enviar, email)


@router.post("/redefinir-senha", status_code=status.HTTP_204_NO_CONTENT)
def redefinir_senha(
    dados: RedefinirSenhaRequest,
    service: SenhaService = Depends(get_senha_service),
) -> None:
    try:
        service.redefinir(dados.token, dados.nova_senha)
    except TokenRedefinicaoInvalidoError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Token de redefinicao invalido") from exc
