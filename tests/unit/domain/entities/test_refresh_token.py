from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.domain.entities.refresh_token import RefreshToken

_AGORA = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)


def _token(expira_em: datetime = _AGORA + timedelta(days=30)) -> RefreshToken:
    return RefreshToken(
        id=uuid4(),
        usuario_id=uuid4(),
        token_hash="a" * 64,
        familia_id=uuid4(),
        criado_em=_AGORA,
        expira_em=expira_em,
    )


def test_token_dentro_da_validade_nao_esta_expirado():
    assert _token().esta_expirado(_AGORA) is False


def test_token_no_instante_de_expiracao_esta_expirado():
    assert _token(expira_em=_AGORA).esta_expirado(_AGORA) is True


def test_revogar_marca_o_instante_e_o_token_fica_revogado():
    token = _token()

    token.revogar(_AGORA)

    assert token.esta_revogado() is True
    assert token.revogado_em == _AGORA


def test_token_novo_nao_esta_revogado():
    assert _token().esta_revogado() is False
