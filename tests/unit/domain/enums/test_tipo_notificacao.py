from app.domain.enums.tipo_notificacao import TipoNotificacao


def test_possui_os_dois_tipos_de_notificacao_suportados():
    assert {membro.value for membro in TipoNotificacao} == {
        "SINAL_ATIVADO",
        "ALERTA_DISPARADO",
    }


def test_membro_e_uma_string_para_serializacao_direta():
    assert isinstance(TipoNotificacao.SINAL_ATIVADO, str)
    assert TipoNotificacao.SINAL_ATIVADO == "SINAL_ATIVADO"
