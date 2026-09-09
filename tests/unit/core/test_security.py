from uuid import uuid4

import pytest

from app.core.security import TokenInvalidoError, criar_token, decodificar_token

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
