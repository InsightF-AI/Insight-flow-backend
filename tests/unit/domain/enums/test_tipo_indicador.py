from app.domain.enums.tipo_indicador import TipoIndicador


def test_possui_os_indicadores_tecnicos_definidos_na_especificacao():
    assert {membro.value for membro in TipoIndicador} == {
        "SMA",
        "RSI",
        "MACD",
        "BOLLINGER",
        "VOLUME_RELATIVO",
    }


def test_membro_e_uma_string_para_serializacao_direta():
    assert isinstance(TipoIndicador.RSI, str)
    assert TipoIndicador.RSI == "RSI"
