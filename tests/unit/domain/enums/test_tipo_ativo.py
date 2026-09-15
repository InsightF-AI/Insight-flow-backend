from app.domain.enums.tipo_ativo import TipoAtivo


def test_possui_os_cinco_tipos_de_ativo_definidos_na_especificacao():
    assert {membro.value for membro in TipoAtivo} == {
        "ACAO",
        "FII",
        "ETF",
        "BDR",
        "CRIPTO",
    }


def test_membro_e_uma_string_para_serializacao_direta():
    assert isinstance(TipoAtivo.ACAO, str)
    assert TipoAtivo.ACAO == "ACAO"
