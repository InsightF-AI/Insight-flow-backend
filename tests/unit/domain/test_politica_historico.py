from app.domain.enums.periodo_historico import PeriodoHistorico
from app.domain.enums.tipo_ativo import TipoAtivo
from app.domain.value_objects.politica_historico import PoliticaHistorico

_POLITICA = PoliticaHistorico(
    periodo_backfill=PeriodoHistorico.TRES_MESES,
    periodo_backfill_cripto=PeriodoHistorico.CINCO_ANOS,
    minimo_cotacoes=50,
)


def test_cripto_usa_o_periodo_de_backfill_de_cripto():
    assert _POLITICA.periodo_backfill_de(TipoAtivo.CRIPTO) is PeriodoHistorico.CINCO_ANOS


def test_demais_tipos_usam_o_periodo_de_backfill_padrao():
    for tipo in (TipoAtivo.ACAO, TipoAtivo.FII, TipoAtivo.ETF, TipoAtivo.BDR, TipoAtivo.INDICE):
        assert _POLITICA.periodo_backfill_de(tipo) is PeriodoHistorico.TRES_MESES
