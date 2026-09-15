from app.domain.enums.tipo_operacao import TipoOperacao


def test_possui_compra_e_venda():
    assert {membro.value for membro in TipoOperacao} == {"COMPRA", "VENDA"}


def test_membro_e_uma_string_para_serializacao_direta():
    assert isinstance(TipoOperacao.COMPRA, str)
    assert TipoOperacao.COMPRA == "COMPRA"
