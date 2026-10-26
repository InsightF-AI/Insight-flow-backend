from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import (
    get_refresh_token_service,
    get_senha_service,
    get_usuario_atual,
    get_usuario_service,
)
from app.api.v1.schemas.auth import AlterarSenhaRequest
from app.api.v1.schemas.token import TokenResponse
from app.api.v1.schemas.usuario import CadastroRequest
from app.domain.entities.usuario import Usuario
from app.services.exceptions import CredenciaisInvalidasError, EmailJaCadastradoError
from app.services.refresh_token_service import RefreshTokenService
from app.services.senha_service import SenhaService
from app.services.usuario_service import UsuarioService

router = APIRouter(prefix="/usuarios", tags=["usuarios"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=TokenResponse)
def cadastrar(
    dados: CadastroRequest,
    service: UsuarioService = Depends(get_usuario_service),
    tokens: RefreshTokenService = Depends(get_refresh_token_service),
) -> TokenResponse:
    try:
        usuario = service.cadastrar(nome=dados.nome, email=dados.email, senha=dados.senha)
    except EmailJaCadastradoError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "E-mail já cadastrado") from exc

    return TokenResponse.de(tokens.emitir(usuario.id))


@router.put("/me/senha", status_code=status.HTTP_204_NO_CONTENT)
def alterar_senha(
    dados: AlterarSenhaRequest,
    usuario: Usuario = Depends(get_usuario_atual),
    service: SenhaService = Depends(get_senha_service),
) -> None:
    try:
        service.alterar(usuario, dados.senha_atual, dados.nova_senha)
    except CredenciaisInvalidasError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Senha atual incorreta") from exc
