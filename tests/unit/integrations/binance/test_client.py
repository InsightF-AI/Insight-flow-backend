from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest

from app.domain.enums.periodo_historico import PeriodoHistorico
from app.integrations.binance.client import BinanceClient, BinanceIndisponivelError
from app.integrations.erros import TickerNaoEncontradoError


def _client(handler) -> BinanceClient:
    transporte = httpx.MockTransport(handler)
    return BinanceClient(httpx.Client(base_url="https://api.binance.com", transport=transporte))


def _kline(open_time_ms: int, fechamento: str) -> list:
    return [
        open_time_ms,
        "10",
        "12",
        "9",
        fechamento,
        "100.5",
        open_time_ms + 1,
        "0",
        1,
        "0",
        "0",
        "0",
    ]


def test_listar_pares_brl_filtra_cotacao_em_brl_e_em_negociacao():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v3/exchangeInfo"
        return httpx.Response(
            200,
            json={
                "symbols": [
                    {
                        "symbol": "BTCBRL",
                        "baseAsset": "BTC",
                        "quoteAsset": "BRL",
                        "status": "TRADING",
                    },
                    {
                        "symbol": "ETHUSDT",
                        "baseAsset": "ETH",
                        "quoteAsset": "USDT",
                        "status": "TRADING",
                    },
                    {
                        "symbol": "LUNABRL",
                        "baseAsset": "LUNA",
                        "quoteAsset": "BRL",
                        "status": "BREAK",
                    },
                ]
            },
        )

    assert _client(handler).listar_pares_brl() == ["BTC"]


def test_buscar_cotacao_atual_mapeia_o_ticker_24h_sem_o_sufixo_brl():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v3/ticker/24hr"
        assert request.url.params["symbol"] == "BTCBRL"
        return httpx.Response(
            200,
            json={
                "symbol": "BTCBRL",
                "lastPrice": "451693.00000000",
                "priceChange": "6587.00000000",
                "priceChangePercent": "1.480",
                "highPrice": "455896.00000000",
                "lowPrice": "438605.00000000",
                "openPrice": "445106.00000000",
                "volume": "100.25603000",
            },
        )

    cotacao = _client(handler).buscar_cotacao_atual("BTC")

    assert cotacao.ticker == "BTC"
    assert cotacao.preco == Decimal("451693.00000000")
    assert cotacao.variacao == Decimal("6587.00000000")
    assert cotacao.variacao_percentual == Decimal("1.480")
    assert cotacao.maxima_dia == Decimal("455896.00000000")
    assert cotacao.minima_dia == Decimal("438605.00000000")
    assert cotacao.abertura == Decimal("445106.00000000")
    assert cotacao.volume == Decimal("100.25603000")


@pytest.mark.parametrize(
    ("periodo", "limite"),
    [
        (PeriodoHistorico.UM_DIA, "1"),
        (PeriodoHistorico.UMA_SEMANA, "7"),
        (PeriodoHistorico.UM_MES, "30"),
        (PeriodoHistorico.TRES_MESES, "90"),
        (PeriodoHistorico.UM_ANO, "365"),
        (PeriodoHistorico.CINCO_ANOS, "1000"),
    ],
)
def test_buscar_historico_pede_klines_diarios_com_o_limite_do_periodo(periodo, limite):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v3/klines"
        assert request.url.params["symbol"] == "BTCBRL"
        assert request.url.params["interval"] == "1d"
        assert request.url.params["limit"] == limite
        return httpx.Response(200, json=[])

    assert _client(handler).buscar_historico("BTC", periodo) == []


def test_buscar_historico_converte_open_time_em_ms_para_utc_e_ordena():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json=[_kline(1704153600000, "120"), _kline(1704067200000, "110")]
        )

    pontos = _client(handler).buscar_historico("BTC", PeriodoHistorico.UM_MES)

    assert [p.data for p in pontos] == [
        datetime(2024, 1, 1, tzinfo=UTC),
        datetime(2024, 1, 2, tzinfo=UTC),
    ]
    assert [p.fechamento for p in pontos] == [Decimal(110), Decimal(120)]
    assert pontos[0].abertura == Decimal(10)
    assert pontos[0].maxima == Decimal(12)
    assert pontos[0].minima == Decimal(9)
    assert pontos[0].volume == Decimal("100.5")


def test_simbolo_invalido_lanca_ticker_nao_encontrado():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"code": -1121, "msg": "Invalid symbol."})

    with pytest.raises(TickerNaoEncontradoError):
        _client(handler).buscar_cotacao_atual("NAOEXISTE")


def test_outro_erro_400_lanca_binance_indisponivel():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"code": -1100, "msg": "Illegal characters."})

    with pytest.raises(BinanceIndisponivelError):
        _client(handler).buscar_cotacao_atual("BTC")


@pytest.mark.parametrize("status_code", [418, 429, 500])
def test_rate_limit_e_erro_do_servidor_lancam_binance_indisponivel(status_code):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"code": -1003, "msg": "Too many requests."})

    with pytest.raises(BinanceIndisponivelError):
        _client(handler).buscar_historico("BTC", PeriodoHistorico.UM_MES)


def test_erro_de_rede_lanca_binance_indisponivel():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rede")

    with pytest.raises(BinanceIndisponivelError):
        _client(handler).listar_pares_brl()
