from app.domain.enums.periodo_historico import PeriodoHistorico


def test_possui_os_periodos_definidos_na_especificacao():
    assert {membro.value for membro in PeriodoHistorico} == {
        "1D",
        "1S",
        "1M",
        "3M",
        "1A",
        "5A",
    }


def test_membro_e_uma_string_para_serializacao_direta():
    assert isinstance(PeriodoHistorico.UM_MES, str)
    assert PeriodoHistorico.UM_MES == "1M"
