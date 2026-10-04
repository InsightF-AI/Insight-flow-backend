from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.core.security import (
    TokenInvalidoError,
    criar_token,
    decodificar_token,
    decodificar_token_com_expiracao,
)

SECRET = "segredo-de-teste"


def test_criar_token_e_decodificar_retorna_o_id_do_usuario():
    usuario_id = uuid4()

    token = criar_token(usuario_id, secret_key=SECRET, expiracao_minutos=60)

    assert decodificar_token(token, secret_key=SECRET) == usuario_id


def test_decodificar_token_com_secret_key_errada_lanca_erro():
    usuario_id = uuid4()
    token = criar_token(usuario_id, secret_key=SECRET, expiracao_minutos=60)

    with pytest.raises(TokenInvalidoError):
        decodificar_token(token, secret_key="outro-segredo")


def test_decodificar_token_expirado_lanca_erro():
    usuario_id = uuid4()
    token = criar_token(usuario_id, secret_key=SECRET, expiracao_minutos=-1)

    with pytest.raises(TokenInvalidoError):
        decodificar_token(token, secret_key=SECRET)


def test_decodificar_token_malformado_lanca_erro():
    with pytest.raises(TokenInvalidoError):
        decodificar_token("token-invalido", secret_key=SECRET)


def test_decodificar_token_com_expiracao_devolve_usuario_e_exp():
    usuario_id = uuid4()
    antes = datetime.now(UTC).replace(microsecond=0)

    token = criar_token(usuario_id, "segredo", expiracao_minutos=30)
    decodificado, expira_em = decodificar_token_com_expiracao(token, "segredo")

    assert decodificado == usuario_id
    assert expira_em.tzinfo is not None
    assert antes + timedelta(minutes=29) < expira_em <= antes + timedelta(minutes=31)


def test_decodificar_token_com_expiracao_com_segredo_errado_lanca_erro():
    token = criar_token(uuid4(), "segredo", expiracao_minutos=30)

    with pytest.raises(TokenInvalidoError):
        decodificar_token_com_expiracao(token, "outro")
