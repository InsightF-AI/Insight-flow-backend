from app.domain.enums.tipo_condicao_alerta import TipoCondicaoAlerta


def test_possui_as_duas_condicoes_de_disparo_suportadas():
    assert {membro.value for membro in TipoCondicaoAlerta} == {
        "PRECO_MAIOR_IGUAL",
        "PRECO_MENOR_IGUAL",
    }


def test_membro_e_uma_string_para_serializacao_direta():
    assert isinstance(TipoCondicaoAlerta.PRECO_MAIOR_IGUAL, str)
    assert TipoCondicaoAlerta.PRECO_MAIOR_IGUAL == "PRECO_MAIOR_IGUAL"
