from decimal import Decimal

from app.domain.enums.periodo_historico import PeriodoHistorico
from app.domain.enums.tipo_ativo import TipoAtivo
from app.integrations.brapi.client import AtivoEncontrado, CotacaoAtual, PontoHistorico
from app.services.dados_mercado_service import DadosMercadoService


class _BrapiClientFalso:
    def __init__(
        self,
        ativos: list[AtivoEncontrado] | None = None,
        cotacao: CotacaoAtual | None = None,
        historico: list[PontoHistorico] | None = None,
    ):
        self._ativos = ativos or []
        self._cotacao = cotacao
        self._historico = historico or []
        self.chamadas: dict[str, object] = {}

    def buscar_ativos(self, termo: str) -> list[AtivoEncontrado]:
        self.chamadas["buscar_ativos"] = termo
        return self._ativos

    def buscar_cotacao_atual(self, ticker: str) -> CotacaoAtual:
        self.chamadas["buscar_cotacao_atual"] = ticker
        return self._cotacao

    def buscar_historico(self, ticker: str, periodo: PeriodoHistorico) -> list[PontoHistorico]:
        self.chamadas["buscar_historico"] = (ticker, periodo)
        return self._historico


def test_buscar_ativo_delega_para_o_cliente_brapi():
    encontrado = AtivoEncontrado(
        ticker="PETR4", nome="Petrobras PN", tipo=TipoAtivo.ACAO, moeda="BRL", setor="Petroleo"
    )
    brapi_client = _BrapiClientFalso(ativos=[encontrado])
    service = DadosMercadoService(brapi_client)

    resultado = service.buscar_ativo("petr4")

    assert resultado == [encontrado]
    assert brapi_client.chamadas["buscar_ativos"] == "petr4"


def test_buscar_cotacao_atual_delega_para_o_cliente_brapi():
    cotacao = CotacaoAtual(
        ticker="PETR4",
        preco=Decimal("36.65"),
        variacao=Decimal("-0.35"),
        variacao_percentual=Decimal("-0.95"),
        maxima_dia=Decimal("37.10"),
        minima_dia=Decimal("36.20"),
        volume=Decimal(27681100),
    )
    brapi_client = _BrapiClientFalso(cotacao=cotacao)
    service = DadosMercadoService(brapi_client)

    resultado = service.buscar_cotacao_atual("PETR4")

    assert resultado == cotacao
    assert brapi_client.chamadas["buscar_cotacao_atual"] == "PETR4"


def test_buscar_historico_delega_para_o_cliente_brapi():
    ponto = PontoHistorico(
        data=None,
        abertura=Decimal(35),
        maxima=Decimal(36),
        minima=Decimal("34.5"),
        fechamento=Decimal("35.8"),
        volume=Decimal(1000000),
    )
    brapi_client = _BrapiClientFalso(historico=[ponto])
    service = DadosMercadoService(brapi_client)

    resultado = service.buscar_historico("PETR4", PeriodoHistorico.UM_MES)

    assert resultado == [ponto]
    assert brapi_client.chamadas["buscar_historico"] == ("PETR4", PeriodoHistorico.UM_MES)
