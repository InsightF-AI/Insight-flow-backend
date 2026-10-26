from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime

from app.core.security import (
    TokenInvalidoError,
    criar_token_redefinicao,
    decodificar_token_redefinicao,
)
from app.domain.entities.usuario import Usuario
from app.integrations.email.enviador import Email
from app.repositories.interfaces.refresh_token_repository import RefreshTokenRepository
from app.repositories.interfaces.usuario_repository import UsuarioRepository
from app.services.exceptions import CredenciaisInvalidasError, TokenRedefinicaoInvalidoError

logger = logging.getLogger(__name__)

_ASSUNTO = "InsightFlow - redefinicao de senha"


class SenhaService:
    def __init__(
        self,
        usuario_repository: UsuarioRepository,
        refresh_token_repository: RefreshTokenRepository,
        jwt_secret_key: str,
        expiracao_minutos: int,
        url_redefinicao: str,
        agora: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self._usuario_repository = usuario_repository
        self._refresh_token_repository = refresh_token_repository
        self._jwt_secret_key = jwt_secret_key
        self._expiracao_minutos = expiracao_minutos
        self._url_redefinicao = url_redefinicao
        self._agora = agora

    def alterar(self, usuario: Usuario, senha_atual: str, nova_senha: str) -> None:
        if not usuario.autenticar(senha_atual):
            raise CredenciaisInvalidasError(usuario.email)
        self._trocar(usuario, nova_senha, "senha_alterada")

    def preparar_recuperacao(self, email: str) -> Email | None:
        usuario = self._usuario_repository.buscar_por_email(email)
        if usuario is None or not usuario.ativo:
            return None

        token = criar_token_redefinicao(
            usuario.id, usuario.impressao_senha(), self._jwt_secret_key, self._expiracao_minutos
        )
        logger.info(
            "Recuperacao de senha solicitada.",
            extra={"evento": "recuperacao_senha", "usuario_id": str(usuario.id)},
        )
        return Email(
            destinatario=usuario.email,
            assunto=_ASSUNTO,
            corpo=(
                f"Ola, {usuario.nome}.\n\n"
                f"Para redefinir sua senha, acesse o link abaixo "
                f"(valido por {self._expiracao_minutos} minutos):\n\n"
                f"{self._url_redefinicao}{token}\n\n"
                f"Se voce nao pediu a redefinicao, ignore este e-mail."
            ),
        )

    def redefinir(self, token: str, nova_senha: str) -> None:
        try:
            usuario_id, impressao = decodificar_token_redefinicao(token, self._jwt_secret_key)
        except TokenInvalidoError as exc:
            raise TokenRedefinicaoInvalidoError from exc

        usuario = self._usuario_repository.buscar_por_id(usuario_id)
        if usuario is None or not usuario.ativo or usuario.impressao_senha() != impressao:
            raise TokenRedefinicaoInvalidoError
        self._trocar(usuario, nova_senha, "senha_redefinida")

    def _trocar(self, usuario: Usuario, nova_senha: str, evento: str) -> None:
        usuario.alterar_senha(nova_senha)
        self._usuario_repository.salvar(usuario)
        self._refresh_token_repository.revogar_do_usuario(usuario.id, self._agora())
        logger.info(
            "Senha trocada; sessoes revogadas.",
            extra={"evento": evento, "usuario_id": str(usuario.id)},
        )
