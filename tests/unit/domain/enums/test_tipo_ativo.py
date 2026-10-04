from app.domain.enums.tipo_ativo import TipoAtivo


def test_possui_os_tipos_da_especificacao_e_o_indice_de_referencia():
    assert {membro.value for membro in TipoAtivo} == {
        "ACAO",
        "FII",
        "ETF",
        "BDR",
        "CRIPTO",
        "INDICE",
    }


def test_membro_e_uma_string_para_serializacao_direta():
    assert isinstance(TipoAtivo.ACAO, str)
    assert TipoAtivo.ACAO == "ACAO"
