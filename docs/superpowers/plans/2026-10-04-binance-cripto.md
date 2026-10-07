# Binance (criptomoedas) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer criptomoedas (pares BRL da Binance) funcionarem em busca, watchlist, cotação, histórico, indicadores, sinais, backtest, alertas e no `ciclo_cripto`.

**Architecture:** Um `BinanceClient` novo devolve as mesmas estruturas de dados da brapi. Um `RoteadorDadosMercadoService` implementa a interface `DadosMercadoService` e manda cada ticker para a Binance (se estiver no catálogo de pares BRL, guardado no Redis) ou para a brapi. Os erros das duas fontes ganham uma base comum, a fonte de dados passa a dizer se o histórico é diário, e uma `PoliticaHistorico` escolhe um período de coleta inicial maior para cripto.

**Tech Stack:** Python 3.12, FastAPI, httpx (`MockTransport` nos testes), pytest, Redis via `MercadoCache`.

**Spec:** `docs/superpowers/specs/2026-10-04-binance-cripto-design.md`

## Global Constraints

- Zero comentários no código-fonte e nos testes.
- Código de domínio, variáveis e nomes de teste em português (`test_<comportamento>`), sem acentos em identificadores.
- Rodar com os binários do venv: `.venv/bin/pytest tests/unit -q`, `.venv/bin/ruff check src tests`, `.venv/bin/ruff format <arquivos alterados>` (não reformatar arquivos que você não tocou).
- Cotação de cripto em BRL (`moeda="BRL"`), pares `{TICKER}BRL`, só os com `quoteAsset == "BRL"` e `status == "TRADING"`.
- Binance sem chave; base URL configurável, padrão `https://api.binance.com`.
- Catálogo de cripto em cache com a chave `catalogo_cripto_brl`, TTL `cache_ttl_catalogo_cripto_segundos` (padrão 86400).
- Coleta inicial de cripto: `historico_backfill_periodo_cripto` padrão `PeriodoHistorico.CINCO_ANOS` (1000 klines diários).
- Mensagens de commit em português, Conventional Commits com escopo, terminando com `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. O usuário comita pessoalmente: nos passos de commit, apenas faça `git add` e proponha a mensagem.

## Review Focus

1. **Binance com rate limit (HTTP 429/418)** — deve virar `BinanceIndisponivelError` (503 na API), nunca "ticker não encontrado". Teste na Task 2.
2. **HTTP 400 com outro código que não `-1121`** (ex.: `-1100`, parâmetro inválido) — é falha da fonte, não ticker inexistente. Teste na Task 2.
3. **`openTime` em milissegundos** — a data do candle precisa sair em UTC com `/ 1000`; um erro aqui grava candles em 1970 ou no ano 50000. Teste na Task 2.
4. **Falha da Binance ao montar o catálogo** — não pode gravar catálogo vazio no cache (senão cripto some por 24h). Teste na Task 5.
5. **Busca em minúsculas (`termo="btc"`)** — deve achar `BTC`. Teste na Task 5.

---

## File Structure

| Arquivo | Responsabilidade |
|---|---|
| `src/app/integrations/erros.py` (novo) | `FonteDadosIndisponivelError` e `TickerNaoEncontradoError`, neutros entre fontes |
| `src/app/integrations/brapi/client.py` | Passa a importar `TickerNaoEncontradoError` de `erros.py`; `BrapiIndisponivelError` herda da base; `AtivoEncontrado.fonte_dados` |
| `src/app/integrations/binance/client.py` (novo) | `BinanceClient` e `BinanceIndisponivelError` |
| `src/app/services/dados_mercado_service.py` | Ganha `historico_e_diario` |
| `src/app/services/cached_dados_mercado_service.py` | Repassa `historico_e_diario` |
| `src/app/services/roteador_dados_mercado_service.py` (novo) | Escolhe Binance ou brapi por ticker; catálogo em cache |
| `src/app/domain/value_objects/politica_historico.py` (novo) | `PoliticaHistorico` |
| `src/app/services/ativo_service.py` | Usa `historico_e_diario` e `PoliticaHistorico` |
| `src/app/services/watchlist_service.py` | Usa `PoliticaHistorico` e `fonte_dados` do resultado |
| `src/app/scheduler/ciclo.py`, `src/app/scheduler/indices_referencia.py` | Recebem `PoliticaHistorico` |
| `src/app/core/config.py` | `binance_base_url`, `cache_ttl_catalogo_cripto_segundos`, `historico_backfill_periodo_cripto`, `politica_historico()` |
| `src/app/api/deps.py`, `src/app/scheduler/jobs.py` | Montam o roteador e a política |
| Controllers `ativos.py`, `watchlist.py`, `alertas.py`; `portfolio_service.py` | Capturam `FonteDadosIndisponivelError` |
| `tests/fixtures/fake_dados_mercado_service.py` | `erro_indisponivel` configurável, `tickers_diarios`, `historico_e_diario` |
| `tests/fixtures/fake_binance_client.py` (novo) | Fake para os testes do roteador |

---

### Task 1: Erros neutros entre fontes de dados

**Files:**
- Create: `src/app/integrations/erros.py`
- Modify: `src/app/integrations/brapi/client.py:35-40`
- Modify: `src/app/api/v1/controllers/ativos.py:19` e os `except BrapiIndisponivelError`
- Modify: `src/app/api/v1/controllers/watchlist.py:12,35`
- Modify: `src/app/api/v1/controllers/alertas.py:8,30`
- Modify: `src/app/services/portfolio_service.py:20` e o `except` de `_rentabilidade_ibovespa`
- Modify: `src/app/services/watchlist_service.py:11` e o `except` de `_coletar_historico`
- Modify: `src/app/scheduler/indices_referencia.py:7` e o `except`
- Modify: `tests/fixtures/fake_dados_mercado_service.py`
- Modify: `tests/unit/integrations/brapi/test_client.py:6-12`
- Test: `tests/unit/api/test_cotacao_controller.py`

**Interfaces:**
- Produces: `app.integrations.erros.FonteDadosIndisponivelError(Exception)`, `app.integrations.erros.TickerNaoEncontradoError(Exception)`; `BrapiIndisponivelError(FonteDadosIndisponivelError)`; `FakeDadosMercadoService.erro_indisponivel: type[Exception]` (padrão `BrapiIndisponivelError`).

- [ ] **Step 1: Write the failing test**

Adicione ao fim de `tests/unit/api/test_cotacao_controller.py`:

```python
def test_cotacao_atual_com_qualquer_fonte_indisponivel_retorna_503(
    client, auth_headers, ativo_repository, dados_mercado_service
):
    ativo_repository.salvar(_PETR4)
    dados_mercado_service.indisponivel = True
    dados_mercado_service.erro_indisponivel = FonteDadosIndisponivelError

    resposta = client.get(f"/api/v1/ativos/{_PETR4.id}/cotacao", headers=auth_headers)

    assert resposta.status_code == 503
```

E o import no topo:

```python
from app.integrations.erros import FonteDadosIndisponivelError
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/api/test_cotacao_controller.py -q`
Expected: erro de coleta `ModuleNotFoundError: No module named 'app.integrations.erros'`.

- [ ] **Step 3: Write minimal implementation**

`src/app/integrations/erros.py`:

```python
class FonteDadosIndisponivelError(Exception):
    pass


class TickerNaoEncontradoError(Exception):
    pass
```

Em `src/app/integrations/brapi/client.py`, troque:

```python
class BrapiIndisponivelError(Exception):
    pass


class TickerNaoEncontradoError(Exception):
    pass
```

por:

```python
class BrapiIndisponivelError(FonteDadosIndisponivelError):
    pass
```

e adicione o import `from app.integrations.erros import FonteDadosIndisponivelError, TickerNaoEncontradoError`.

Em `tests/fixtures/fake_dados_mercado_service.py`:
- importe `TickerNaoEncontradoError` de `app.integrations.erros` (e não mais do módulo da brapi);
- no `__init__`, adicione `self.erro_indisponivel: type[Exception] = BrapiIndisponivelError`;
- troque todo `raise BrapiIndisponivelError` por `raise self.erro_indisponivel`.

Troque os imports e capturas em `src/`:
- `controllers/ativos.py`: `from app.integrations.erros import FonteDadosIndisponivelError, TickerNaoEncontradoError` e todo `except BrapiIndisponivelError` vira `except FonteDadosIndisponivelError`.
- `controllers/watchlist.py` e `controllers/alertas.py`: `from app.integrations.erros import FonteDadosIndisponivelError` e o `except` correspondente.
- `services/portfolio_service.py`, `services/watchlist_service.py`, `scheduler/indices_referencia.py`: `from app.integrations.erros import FonteDadosIndisponivelError, TickerNaoEncontradoError` e `except (FonteDadosIndisponivelError, TickerNaoEncontradoError):`.

Em `tests/unit/integrations/brapi/test_client.py`, importe `TickerNaoEncontradoError` de `app.integrations.erros` e mantenha `BrapiIndisponivelError` vindo da brapi.

Confirme que não sobrou import de `TickerNaoEncontradoError` do módulo da brapi:

Run: `grep -rn "brapi.client import.*TickerNaoEncontradoError" src tests; grep -rn "^    TickerNaoEncontradoError,$" src tests`
Expected: só ocorrências dentro de blocos `from app.integrations.erros import (`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit -q && .venv/bin/ruff check src tests`
Expected: todos passam; `All checks passed!`.

- [ ] **Step 5: Commit**

```bash
git add src/app/integrations/erros.py src/app/integrations/brapi/client.py src/app/api/v1/controllers src/app/services/portfolio_service.py src/app/services/watchlist_service.py src/app/scheduler/indices_referencia.py tests/fixtures/fake_dados_mercado_service.py tests/unit/integrations/brapi/test_client.py tests/unit/api/test_cotacao_controller.py
```

Mensagem: `refactor(mercado): cria erros neutros entre fontes de dados`

---

### Task 2: BinanceClient

**Files:**
- Create: `src/app/integrations/binance/client.py`
- Create: `tests/unit/integrations/binance/__init__.py` (vazio)
- Create: `tests/unit/integrations/binance/test_client.py`
- Modify: `src/app/core/config.py` (adicionar `binance_base_url`)
- Modify: `tests/unit/api/test_cotacao_controller.py`

**Interfaces:**
- Consumes: `FonteDadosIndisponivelError`, `TickerNaoEncontradoError` (Task 1); `CotacaoAtual`, `PontoHistorico` de `app.integrations.brapi.client`.
- Produces: `BinanceIndisponivelError(FonteDadosIndisponivelError)`; `BinanceClient(http_client: httpx.Client)` com `listar_pares_brl() -> list[str]`, `buscar_cotacao_atual(ticker: str) -> CotacaoAtual`, `buscar_historico(ticker: str, periodo: PeriodoHistorico) -> list[PontoHistorico]`; `Settings.binance_base_url: str = "https://api.binance.com"`.

- [ ] **Step 1: Write the failing tests**

`tests/unit/integrations/binance/test_client.py`:

```python
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
    return [open_time_ms, "10", "12", "9", fechamento, "100.5", open_time_ms + 1, "0", 1, "0", "0", "0"]


def test_listar_pares_brl_filtra_cotacao_em_brl_e_em_negociacao():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v3/exchangeInfo"
        return httpx.Response(
            200,
            json={
                "symbols": [
                    {"symbol": "BTCBRL", "baseAsset": "BTC", "quoteAsset": "BRL", "status": "TRADING"},
                    {"symbol": "ETHUSDT", "baseAsset": "ETH", "quoteAsset": "USDT", "status": "TRADING"},
                    {"symbol": "LUNABRL", "baseAsset": "LUNA", "quoteAsset": "BRL", "status": "BREAK"},
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
```

Adicione ao fim de `tests/unit/api/test_cotacao_controller.py`:

```python
def test_cotacao_atual_com_binance_indisponivel_retorna_503(
    client, auth_headers, ativo_repository, dados_mercado_service
):
    ativo_repository.salvar(_PETR4)
    dados_mercado_service.indisponivel = True
    dados_mercado_service.erro_indisponivel = BinanceIndisponivelError

    resposta = client.get(f"/api/v1/ativos/{_PETR4.id}/cotacao", headers=auth_headers)

    assert resposta.status_code == 503
```

com o import `from app.integrations.binance.client import BinanceIndisponivelError`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/integrations/binance tests/unit/api/test_cotacao_controller.py -q`
Expected: `ModuleNotFoundError: No module named 'app.integrations.binance.client'`.

- [ ] **Step 3: Write minimal implementation**

`src/app/integrations/binance/client.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import httpx

from app.domain.enums.periodo_historico import PeriodoHistorico
from app.integrations.brapi.client import CotacaoAtual, PontoHistorico
from app.integrations.erros import FonteDadosIndisponivelError, TickerNaoEncontradoError

_MOEDA_COTACAO = "BRL"
_CODIGO_SIMBOLO_INVALIDO = -1121

_LIMITE_POR_PERIODO: dict[PeriodoHistorico, int] = {
    PeriodoHistorico.UM_DIA: 1,
    PeriodoHistorico.UMA_SEMANA: 7,
    PeriodoHistorico.UM_MES: 30,
    PeriodoHistorico.TRES_MESES: 90,
    PeriodoHistorico.UM_ANO: 365,
    PeriodoHistorico.CINCO_ANOS: 1000,
}


class BinanceIndisponivelError(FonteDadosIndisponivelError):
    pass


class BinanceClient:
    def __init__(self, http_client: httpx.Client):
        self._http_client = http_client

    def listar_pares_brl(self) -> list[str]:
        dados = self._get("/api/v3/exchangeInfo", {})
        return [
            simbolo["baseAsset"]
            for simbolo in dados.get("symbols", [])
            if simbolo.get("quoteAsset") == _MOEDA_COTACAO and simbolo.get("status") == "TRADING"
        ]

    def buscar_cotacao_atual(self, ticker: str) -> CotacaoAtual:
        dados = self._get("/api/v3/ticker/24hr", {"symbol": f"{ticker}{_MOEDA_COTACAO}"})
        return CotacaoAtual(
            ticker=ticker,
            preco=Decimal(dados["lastPrice"]),
            variacao=Decimal(dados["priceChange"]),
            variacao_percentual=Decimal(dados["priceChangePercent"]),
            maxima_dia=Decimal(dados["highPrice"]),
            minima_dia=Decimal(dados["lowPrice"]),
            volume=Decimal(dados["volume"]),
            abertura=Decimal(dados["openPrice"]),
        )

    def buscar_historico(self, ticker: str, periodo: PeriodoHistorico) -> list[PontoHistorico]:
        klines = self._get(
            "/api/v3/klines",
            {
                "symbol": f"{ticker}{_MOEDA_COTACAO}",
                "interval": "1d",
                "limit": str(_LIMITE_POR_PERIODO[periodo]),
            },
        )
        return [
            PontoHistorico(
                data=datetime.fromtimestamp(kline[0] / 1000, tz=UTC),
                abertura=Decimal(kline[1]),
                maxima=Decimal(kline[2]),
                minima=Decimal(kline[3]),
                fechamento=Decimal(kline[4]),
                volume=Decimal(kline[5]),
            )
            for kline in sorted(klines, key=lambda kline: kline[0])
        ]

    def _get(self, caminho: str, params: dict[str, str]):
        try:
            resposta = self._http_client.get(caminho, params=params)
            resposta.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 400 and _codigo_erro(exc.response) == (
                _CODIGO_SIMBOLO_INVALIDO
            ):
                raise TickerNaoEncontradoError(params.get("symbol")) from exc
            raise BinanceIndisponivelError from exc
        except httpx.HTTPError as exc:
            raise BinanceIndisponivelError from exc

        return resposta.json()


def _codigo_erro(resposta: httpx.Response) -> int | None:
    try:
        return resposta.json().get("code")
    except ValueError:
        return None
```

Em `src/app/core/config.py`, logo abaixo de `brapi_api_key`, adicione:

```python
    binance_base_url: str = "https://api.binance.com"
```

E em `.env.example`, abaixo de `BRAPI_API_KEY=`, adicione `BINANCE_BASE_URL=https://api.binance.com`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit -q && .venv/bin/ruff check src tests`
Expected: todos passam.

- [ ] **Step 5: Commit**

```bash
git add src/app/integrations/binance/client.py src/app/core/config.py .env.example tests/unit/integrations/binance tests/unit/api/test_cotacao_controller.py
```

Mensagem: `feat(binance): adiciona BinanceClient para pares BRL`

---

### Task 3: Fonte de dados diz se o histórico é diário; origem do ativo na busca

**Files:**
- Modify: `src/app/services/dados_mercado_service.py`
- Modify: `src/app/services/cached_dados_mercado_service.py`
- Modify: `src/app/services/ativo_service.py` (`_coletar_historico` e imports)
- Modify: `src/app/integrations/brapi/client.py` (`AtivoEncontrado`)
- Modify: `src/app/services/watchlist_service.py` (`_resolver_ativo_na_brapi`)
- Modify: `tests/fixtures/fake_dados_mercado_service.py`
- Test: `tests/unit/services/test_dados_mercado_service.py`, `tests/unit/services/test_cached_dados_mercado_service.py`, `tests/unit/services/test_ativo_service.py`, `tests/unit/services/test_watchlist_service.py`

**Interfaces:**
- Consumes: nada novo.
- Produces: `DadosMercadoService.historico_e_diario(ticker: str, periodo: PeriodoHistorico) -> bool`; `FakeDadosMercadoService(..., tickers_diarios: set[str] | None = None)`; `AtivoEncontrado.fonte_dados: str = "brapi"`; `WatchlistService._resolver_ativo(ticker) -> Ativo`.

- [ ] **Step 1: Write the failing tests**

Em `tests/unit/services/test_dados_mercado_service.py`, adicione (reaproveite o helper/fake do arquivo para construir o serviço; o `BrapiClient` não é chamado):

```python
def test_historico_e_diario_segue_o_intervalo_da_brapi():
    service = DadosMercadoService(brapi_client=None)

    assert service.historico_e_diario("PETR4", PeriodoHistorico.TRES_MESES) is True
    assert service.historico_e_diario("PETR4", PeriodoHistorico.CINCO_ANOS) is False
    assert service.historico_e_diario("PETR4", PeriodoHistorico.UM_DIA) is False
```

Em `tests/unit/services/test_cached_dados_mercado_service.py`:

```python
def test_historico_e_diario_delega_ao_servico_interno():
    interno = FakeDadosMercadoService(tickers_diarios={"BTC"})
    service = CachedDadosMercadoService(interno, FakeMercadoCache(), ttl_cotacao_atual=60)

    assert service.historico_e_diario("BTC", PeriodoHistorico.CINCO_ANOS) is True
    assert service.historico_e_diario("PETR4", PeriodoHistorico.CINCO_ANOS) is False
```

Em `tests/unit/services/test_ativo_service.py`:

```python
def test_coleta_de_historico_nao_diario_nao_persiste():
    ativo_repository = FakeAtivoRepository()
    ativo_repository.salvar(_PETR4)
    dados_mercado_service = FakeDadosMercadoService(
        historicos={"PETR4": [_ponto_dias_atras(3000, "20")]}
    )
    cotacao_repository = FakeCotacaoRepository()
    service = _service(ativo_repository, dados_mercado_service, cotacao_repository)

    service.atualizar_historico(
        _PETR4.id, periodo_backfill=PeriodoHistorico.CINCO_ANOS, minimo_cotacoes=50
    )

    assert cotacao_repository.listar_por_ativo(_PETR4.id) == []


def test_coleta_de_historico_persiste_quando_a_fonte_diz_que_e_diario():
    ativo_repository = FakeAtivoRepository()
    ativo_repository.salvar(_PETR4)
    dados_mercado_service = FakeDadosMercadoService(
        historicos={"PETR4": [_ponto_dias_atras(3000, "20")]}, tickers_diarios={"PETR4"}
    )
    cotacao_repository = FakeCotacaoRepository()
    service = _service(ativo_repository, dados_mercado_service, cotacao_repository)

    service.atualizar_historico(
        _PETR4.id, periodo_backfill=PeriodoHistorico.CINCO_ANOS, minimo_cotacoes=50
    )

    assert len(cotacao_repository.listar_por_ativo(_PETR4.id)) == 1
```

(A Task 4 troca a assinatura de `atualizar_historico`; esses dois testes serão ajustados lá.)

Em `tests/unit/services/test_watchlist_service.py`:

```python
def test_adicionar_grava_a_fonte_de_dados_informada_pela_busca():
    btc = AtivoEncontrado(
        ticker="BTC", nome="BTC", tipo=TipoAtivo.CRIPTO, moeda="BRL", setor=None,
        fonte_dados="binance",
    )
    service = _service([btc])

    item = service.adicionar(usuario_id=uuid4(), ticker="BTC")

    assert item.ativo.fonte_dados == "binance"
    assert item.ativo.tipo is TipoAtivo.CRIPTO
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/services -q`
Expected: falham com `AttributeError: ... 'historico_e_diario'`, `TypeError: ... unexpected keyword argument 'tickers_diarios'` e `unexpected keyword argument 'fonte_dados'`.

- [ ] **Step 3: Write minimal implementation**

`src/app/services/dados_mercado_service.py` — adicione o import `INTERVALO_DIARIO, intervalo_de` e o método:

```python
    def historico_e_diario(self, ticker: str, periodo: PeriodoHistorico) -> bool:
        return intervalo_de(periodo) == INTERVALO_DIARIO
```

`src/app/services/cached_dados_mercado_service.py`:

```python
    def historico_e_diario(self, ticker: str, periodo: PeriodoHistorico) -> bool:
        return self._interno.historico_e_diario(ticker, periodo)
```

`tests/fixtures/fake_dados_mercado_service.py` — novo parâmetro `tickers_diarios: set[str] | None = None` no `__init__` (`self._tickers_diarios = tickers_diarios or set()`) e:

```python
    def historico_e_diario(self, ticker: str, periodo: PeriodoHistorico) -> bool:
        return ticker in self._tickers_diarios or intervalo_de(periodo) == INTERVALO_DIARIO
```

(importe `INTERVALO_DIARIO, intervalo_de` de `app.integrations.brapi.client`).

`src/app/services/ativo_service.py` — em `_coletar_historico`, troque `if intervalo_de(periodo) == INTERVALO_DIARIO:` por `if self._dados_mercado_service.historico_e_diario(ativo.ticker, periodo):` e remova os imports `INTERVALO_DIARIO` e `intervalo_de` que ficarem sem uso.

`src/app/integrations/brapi/client.py` — em `AtivoEncontrado`, adicione o último campo `fonte_dados: str = "brapi"`.

`src/app/services/watchlist_service.py` — renomeie `_resolver_ativo_na_brapi` para `_resolver_ativo` (e a chamada em `adicionar`) e troque `fonte_dados="brapi"` por `fonte_dados=correspondente.fonte_dados`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit -q && .venv/bin/ruff check src tests`
Expected: todos passam.

- [ ] **Step 5: Commit**

```bash
git add src/app/services/dados_mercado_service.py src/app/services/cached_dados_mercado_service.py src/app/services/ativo_service.py src/app/integrations/brapi/client.py src/app/services/watchlist_service.py tests/fixtures/fake_dados_mercado_service.py tests/unit/services
```

Mensagem: `refactor(mercado): fonte de dados decide se o historico e diario`

---

### Task 4: PoliticaHistorico com coleta inicial maior para cripto

**Files:**
- Create: `src/app/domain/value_objects/politica_historico.py`
- Create: `tests/unit/domain/test_politica_historico.py`
- Modify: `src/app/services/ativo_service.py` (`atualizar_historico`)
- Modify: `src/app/services/watchlist_service.py` (`__init__`, `_coletar_historico`)
- Modify: `src/app/scheduler/ciclo.py` (`executar_ciclo_monitoramento`, `_processar_ativo`)
- Modify: `src/app/scheduler/indices_referencia.py`
- Modify: `src/app/core/config.py`
- Modify: `src/app/api/deps.py` (`get_watchlist_service`)
- Modify: `src/app/scheduler/jobs.py` (`_executar_ciclo`, `_executar_indices_referencia`)
- Modify: `.env.example`
- Test: `tests/unit/services/test_ativo_service.py`, `tests/unit/services/test_watchlist_service.py`, `tests/unit/scheduler/test_ciclo.py`, `tests/unit/scheduler/test_indices_referencia.py`, `tests/unit/core/test_config.py` (novo se não existir)

**Interfaces:**
- Consumes: `historico_e_diario` e `tickers_diarios` (Task 3).
- Produces: `PoliticaHistorico(periodo_backfill: PeriodoHistorico, periodo_backfill_cripto: PeriodoHistorico, minimo_cotacoes: int)` com `periodo_backfill_de(tipo: TipoAtivo) -> PeriodoHistorico`; `AtivoService.atualizar_historico(ativo_id: UUID, politica: PoliticaHistorico) -> None`; `WatchlistService(watchlist_repository, ativo_repository, dados_mercado_service, ativo_service, politica: PoliticaHistorico)`; `executar_ciclo_monitoramento(..., notificacao_service, politica: PoliticaHistorico, ao_falhar_ativo=None)`; `atualizar_indices_referencia(ativo_service, politica)`; `Settings.historico_backfill_periodo_cripto: PeriodoHistorico = CINCO_ANOS`; `Settings.politica_historico() -> PoliticaHistorico`.

- [ ] **Step 1: Write the failing tests**

`tests/unit/domain/test_politica_historico.py`:

```python
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
```

Em `tests/unit/core/test_config.py` (crie o arquivo se não existir, com `tests/unit/core/__init__.py` já presente):

```python
from app.core.config import Settings
from app.domain.enums.periodo_historico import PeriodoHistorico


def test_politica_historico_usa_os_valores_configurados():
    settings = Settings(
        _env_file=None,
        historico_backfill_periodo=PeriodoHistorico.UM_MES,
        historico_backfill_periodo_cripto=PeriodoHistorico.UM_ANO,
        historico_minimo_cotacoes=30,
    )

    politica = settings.politica_historico()

    assert politica.periodo_backfill is PeriodoHistorico.UM_MES
    assert politica.periodo_backfill_cripto is PeriodoHistorico.UM_ANO
    assert politica.minimo_cotacoes == 30


def test_backfill_de_cripto_padrao_e_cinco_anos():
    assert Settings(_env_file=None).historico_backfill_periodo_cripto is PeriodoHistorico.CINCO_ANOS
```

Em `tests/unit/services/test_ativo_service.py`, defina no topo dos testes de `atualizar_historico` uma constante e um ativo cripto:

```python
_POLITICA = PoliticaHistorico(
    periodo_backfill=PeriodoHistorico.TRES_MESES,
    periodo_backfill_cripto=PeriodoHistorico.CINCO_ANOS,
    minimo_cotacoes=50,
)

_BTC = Ativo(
    id=uuid4(),
    ticker="BTC",
    nome="BTC",
    tipo=TipoAtivo.CRIPTO,
    setor=None,
    moeda="BRL",
    fonte_dados="binance",
)
```

Troque toda chamada `atualizar_historico(<id>, periodo_backfill=PeriodoHistorico.TRES_MESES, minimo_cotacoes=50)` por `atualizar_historico(<id>, _POLITICA)`. Nos dois testes da Task 3 que usavam `periodo_backfill=PeriodoHistorico.CINCO_ANOS`, use `PoliticaHistorico(periodo_backfill=PeriodoHistorico.CINCO_ANOS, periodo_backfill_cripto=PeriodoHistorico.CINCO_ANOS, minimo_cotacoes=50)`. Adicione:

```python
def test_atualizar_historico_de_cripto_com_poucas_cotacoes_busca_cinco_anos_e_persiste():
    ativo_repository = FakeAtivoRepository()
    ativo_repository.salvar(_BTC)
    dados_mercado_service = FakeDadosMercadoService(
        historicos={"BTC": [_ponto_dias_atras(900, "200000"), _ponto_dias_atras(1, "450000")]},
        tickers_diarios={"BTC"},
    )
    cotacao_repository = FakeCotacaoRepository()
    service = _service(ativo_repository, dados_mercado_service, cotacao_repository)

    service.atualizar_historico(_BTC.id, _POLITICA)

    assert dados_mercado_service.historicos_solicitados == [("BTC", PeriodoHistorico.CINCO_ANOS)]
    assert len(cotacao_repository.listar_por_ativo(_BTC.id)) == 2
```

Em `tests/unit/services/test_watchlist_service.py`, no helper `_service`, troque `periodo_backfill=PeriodoHistorico.TRES_MESES, minimo_cotacoes=50` por `politica=PoliticaHistorico(periodo_backfill=PeriodoHistorico.TRES_MESES, periodo_backfill_cripto=PeriodoHistorico.CINCO_ANOS, minimo_cotacoes=50)`.

Em `tests/unit/scheduler/test_ciclo.py`:
- defina `_POLITICA` igual à de cima;
- no helper `_executar`, troque o parâmetro `minimo_cotacoes: int = 50` por `politica: PoliticaHistorico = _POLITICA` e passe `politica=politica` no lugar de `periodo_backfill=...` e `minimo_cotacoes=...`;
- no teste `test_falha_em_ativo_invoca_callback_ao_falhar_ativo`, troque os dois kwargs por `politica=_POLITICA`;
- no teste `test_ativo_em_watchlist_com_cotacoes_suficientes_coleta_apenas_um_mes`, troque `_executar(ciclo, {TipoAtivo.ACAO}, minimo_cotacoes=len(historico))` por `_executar(ciclo, {TipoAtivo.ACAO}, politica=PoliticaHistorico(periodo_backfill=PeriodoHistorico.TRES_MESES, periodo_backfill_cripto=PeriodoHistorico.CINCO_ANOS, minimo_cotacoes=len(historico)))`;
- adicione:

```python
def test_cripto_em_watchlist_no_ciclo_de_cripto_coleta_cinco_anos():
    dados_mercado_service = FakeDadosMercadoService(
        cotacoes={"BTC": _cotacao("BTC", "450000")},
        historicos={"BTC": _historico_rsi_baixo()},
        tickers_diarios={"BTC"},
    )
    ciclo = _construir_ciclo(dados_mercado_service)
    btc = _ativo("BTC", TipoAtivo.CRIPTO)
    ciclo.ativo_repository.salvar(btc)
    ciclo.watchlist_repository.salvar(
        Watchlist.adicionar(
            id=uuid4(), usuario_id=uuid4(), ativo_id=btc.id, adicionado_em=datetime.now(UTC)
        )
    )

    _executar(ciclo, {TipoAtivo.CRIPTO})

    assert dados_mercado_service.historicos_solicitados == [("BTC", PeriodoHistorico.CINCO_ANOS)]
    assert len(ciclo.cotacao_repository.listar_por_ativo(btc.id)) == len(_historico_rsi_baixo())
```

Em `tests/unit/scheduler/test_indices_referencia.py`, troque `atualizar_indices_referencia(ativo_service, PeriodoHistorico.TRES_MESES, minimo_cotacoes=50)` (duas ocorrências) por `atualizar_indices_referencia(ativo_service, _POLITICA)`, definindo `_POLITICA` no topo como acima.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit -q`
Expected: falham com `ModuleNotFoundError: No module named 'app.domain.value_objects.politica_historico'`.

- [ ] **Step 3: Write minimal implementation**

`src/app/domain/value_objects/politica_historico.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from app.domain.enums.periodo_historico import PeriodoHistorico
from app.domain.enums.tipo_ativo import TipoAtivo


@dataclass(frozen=True)
class PoliticaHistorico:
    periodo_backfill: PeriodoHistorico
    periodo_backfill_cripto: PeriodoHistorico
    minimo_cotacoes: int

    def periodo_backfill_de(self, tipo: TipoAtivo) -> PeriodoHistorico:
        if tipo == TipoAtivo.CRIPTO:
            return self.periodo_backfill_cripto
        return self.periodo_backfill
```

`src/app/core/config.py` — abaixo de `historico_backfill_periodo`, adicione `historico_backfill_periodo_cripto: PeriodoHistorico = PeriodoHistorico.CINCO_ANOS`; importe `PoliticaHistorico` e adicione à classe `Settings`:

```python
    def politica_historico(self) -> PoliticaHistorico:
        return PoliticaHistorico(
            periodo_backfill=self.historico_backfill_periodo,
            periodo_backfill_cripto=self.historico_backfill_periodo_cripto,
            minimo_cotacoes=self.historico_minimo_cotacoes,
        )
```

`.env.example` — abaixo de `HISTORICO_BACKFILL_PERIODO=3M`, adicione `HISTORICO_BACKFILL_PERIODO_CRIPTO=5A`.

`src/app/services/ativo_service.py`:

```python
    def atualizar_historico(self, ativo_id: UUID, politica: PoliticaHistorico) -> None:
        ativo = self._buscar_ativo(ativo_id)
        persistidas = len(self._cotacao_repository.listar_por_ativo(ativo.id))
        periodo = (
            politica.periodo_backfill_de(ativo.tipo)
            if persistidas < politica.minimo_cotacoes
            else PeriodoHistorico.UM_MES
        )
        self._coletar_historico(ativo, periodo)
```

`src/app/services/watchlist_service.py` — o `__init__` troca `periodo_backfill: PeriodoHistorico, minimo_cotacoes: int` por `politica: PoliticaHistorico` (guardado em `self._politica`), e `_coletar_historico` chama `self._ativo_service.atualizar_historico(ativo.id, self._politica)`. Remova o import de `PeriodoHistorico` se ficar sem uso.

`src/app/scheduler/ciclo.py` — em `executar_ciclo_monitoramento` e `_processar_ativo`, troque `periodo_backfill: PeriodoHistorico, minimo_cotacoes: int` por `politica: PoliticaHistorico`, repasse `politica=politica` e chame `ativo_service.atualizar_historico(ativo_id, politica)`. Remova o import de `PeriodoHistorico` se ficar sem uso.

`src/app/scheduler/indices_referencia.py`:

```python
def atualizar_indices_referencia(ativo_service: AtivoService, politica: PoliticaHistorico) -> None:
    ibovespa = ativo_service.buscar_ou_criar_indice(IBOVESPA_TICKER, IBOVESPA_NOME)
    try:
        ativo_service.atualizar_historico(ibovespa.id, politica)
    except (FonteDadosIndisponivelError, TickerNaoEncontradoError):
        logger.warning("Falha ao atualizar o historico do Ibovespa.", exc_info=True)
```

`src/app/api/deps.py` (`get_watchlist_service`): troque os dois kwargs por `politica=settings.politica_historico()`.

`src/app/scheduler/jobs.py`: em `_executar_ciclo`, troque `periodo_backfill=...` e `minimo_cotacoes=...` por `politica=settings.politica_historico()`; em `_executar_indices_referencia`, troque os dois argumentos posicionais por `settings.politica_historico()`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit -q && .venv/bin/ruff check src tests && grep -rn "periodo_backfill=\|minimo_cotacoes=" src`
Expected: todos passam; o `grep` só encontra `src/app/core/config.py` (dentro de `politica_historico`).

- [ ] **Step 5: Commit**

```bash
git add src/app/domain/value_objects/politica_historico.py src/app/core/config.py .env.example src/app/services/ativo_service.py src/app/services/watchlist_service.py src/app/scheduler src/app/api/deps.py tests/unit
```

Mensagem: `feat(historico): adiciona PoliticaHistorico com backfill de cinco anos para cripto`

---

### Task 5: RoteadorDadosMercadoService

**Files:**
- Create: `src/app/services/roteador_dados_mercado_service.py`
- Create: `tests/fixtures/fake_binance_client.py`
- Create: `tests/unit/services/test_roteador_dados_mercado_service.py`
- Modify: `src/app/core/config.py` (`cache_ttl_catalogo_cripto_segundos`)
- Modify: `.env.example`

**Interfaces:**
- Consumes: `BinanceClient`, `BinanceIndisponivelError` (Task 2); `historico_e_diario`, `AtivoEncontrado.fonte_dados` (Task 3); `MercadoCache`; `FakeMercadoCache` (já existe em `tests/fixtures/fake_mercado_cache.py`, com `ttls`).
- Produces: `RoteadorDadosMercadoService(brapi: DadosMercadoService, binance_client: BinanceClient, cache: MercadoCache, ttl_catalogo_segundos: int)`; `Settings.cache_ttl_catalogo_cripto_segundos: int = 86400`.

- [ ] **Step 1: Write the fake and the failing tests**

`tests/fixtures/fake_binance_client.py`:

```python
from __future__ import annotations

from app.domain.enums.periodo_historico import PeriodoHistorico
from app.integrations.binance.client import BinanceClient, BinanceIndisponivelError
from app.integrations.brapi.client import CotacaoAtual, PontoHistorico
from app.integrations.erros import TickerNaoEncontradoError


class FakeBinanceClient(BinanceClient):
    def __init__(
        self,
        pares: list[str] | None = None,
        cotacoes: dict[str, CotacaoAtual] | None = None,
        historicos: dict[str, list[PontoHistorico]] | None = None,
        indisponivel: bool = False,
    ):
        self._pares = pares if pares is not None else []
        self._cotacoes = cotacoes if cotacoes is not None else {}
        self._historicos = historicos if historicos is not None else {}
        self.indisponivel = indisponivel
        self.chamadas_catalogo = 0

    def listar_pares_brl(self) -> list[str]:
        self.chamadas_catalogo += 1
        if self.indisponivel:
            raise BinanceIndisponivelError
        return list(self._pares)

    def buscar_cotacao_atual(self, ticker: str) -> CotacaoAtual:
        if self.indisponivel:
            raise BinanceIndisponivelError
        if ticker not in self._cotacoes:
            raise TickerNaoEncontradoError(ticker)
        return self._cotacoes[ticker]

    def buscar_historico(self, ticker: str, periodo: PeriodoHistorico) -> list[PontoHistorico]:
        if self.indisponivel:
            raise BinanceIndisponivelError
        if ticker not in self._historicos:
            raise TickerNaoEncontradoError(ticker)
        return self._historicos[ticker]
```

`tests/unit/services/test_roteador_dados_mercado_service.py`:

```python
import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.domain.enums.periodo_historico import PeriodoHistorico
from app.domain.enums.tipo_ativo import TipoAtivo
from app.integrations.binance.client import BinanceIndisponivelError
from app.integrations.brapi.client import AtivoEncontrado, CotacaoAtual, PontoHistorico
from app.services.roteador_dados_mercado_service import RoteadorDadosMercadoService
from tests.fixtures.fake_binance_client import FakeBinanceClient
from tests.fixtures.fake_dados_mercado_service import FakeDadosMercadoService
from tests.fixtures.fake_mercado_cache import FakeMercadoCache

_PETR4 = AtivoEncontrado(
    ticker="PETR4", nome="Petrobras PN", tipo=TipoAtivo.ACAO, moeda="BRL", setor="Petroleo e Gas"
)


def _cotacao(ticker: str, preco: str) -> CotacaoAtual:
    return CotacaoAtual(
        ticker=ticker,
        preco=Decimal(preco),
        variacao=Decimal(0),
        variacao_percentual=Decimal(0),
        maxima_dia=Decimal(preco),
        minima_dia=Decimal(preco),
        volume=Decimal(1),
    )


def _ponto(fechamento: str) -> PontoHistorico:
    return PontoHistorico(
        data=datetime(2026, 10, 1, tzinfo=UTC),
        abertura=Decimal(fechamento),
        maxima=Decimal(fechamento),
        minima=Decimal(fechamento),
        fechamento=Decimal(fechamento),
        volume=Decimal(1),
    )


def _roteador(brapi=None, binance=None, cache=None) -> RoteadorDadosMercadoService:
    return RoteadorDadosMercadoService(
        brapi or FakeDadosMercadoService(),
        binance or FakeBinanceClient(),
        cache or FakeMercadoCache(),
        ttl_catalogo_segundos=86400,
    )


def test_cotacao_de_cripto_vem_da_binance_e_de_acao_vem_da_brapi():
    roteador = _roteador(
        brapi=FakeDadosMercadoService(cotacoes={"PETR4": _cotacao("PETR4", "36")}),
        binance=FakeBinanceClient(pares=["BTC"], cotacoes={"BTC": _cotacao("BTC", "450000")}),
    )

    assert roteador.buscar_cotacao_atual("BTC").preco == Decimal(450000)
    assert roteador.buscar_cotacao_atual("PETR4").preco == Decimal(36)


def test_historico_de_cripto_vem_da_binance_e_de_acao_vem_da_brapi():
    brapi = FakeDadosMercadoService(historicos={"PETR4": [_ponto("36")]})
    roteador = _roteador(
        brapi=brapi,
        binance=FakeBinanceClient(pares=["BTC"], historicos={"BTC": [_ponto("450000")]}),
    )

    assert roteador.buscar_historico("BTC", PeriodoHistorico.UM_MES)[0].fechamento == Decimal(450000)
    assert roteador.buscar_historico("PETR4", PeriodoHistorico.UM_MES)[0].fechamento == Decimal(36)
    assert brapi.historicos_solicitados == [("PETR4", PeriodoHistorico.UM_MES)]


def test_busca_junta_brapi_e_criptos_que_contem_o_termo_sem_diferenciar_maiusculas():
    roteador = _roteador(
        brapi=FakeDadosMercadoService([_PETR4]),
        binance=FakeBinanceClient(pares=["BTC", "ETH", "USDT"]),
    )

    encontrados = roteador.buscar_ativo("t")

    assert [a.ticker for a in encontrados] == ["PETR4", "BTC", "ETH", "USDT"]
    btc = encontrados[1]
    assert btc.tipo is TipoAtivo.CRIPTO
    assert btc.moeda == "BRL"
    assert btc.setor is None
    assert btc.nome == "BTC"
    assert btc.fonte_dados == "binance"
    assert [a.ticker for a in roteador.buscar_ativo("btc")] == ["BTC"]


def test_busca_segue_so_com_a_brapi_quando_a_binance_esta_fora():
    roteador = _roteador(
        brapi=FakeDadosMercadoService([_PETR4]),
        binance=FakeBinanceClient(indisponivel=True),
    )

    assert [a.ticker for a in roteador.buscar_ativo("petr")] == ["PETR4"]


def test_catalogo_e_gravado_no_cache_com_o_ttl_e_reaproveitado():
    cache = FakeMercadoCache()
    binance = FakeBinanceClient(pares=["BTC"], cotacoes={"BTC": _cotacao("BTC", "450000")})
    roteador = _roteador(binance=binance, cache=cache)

    roteador.buscar_cotacao_atual("BTC")
    roteador.buscar_cotacao_atual("BTC")

    assert binance.chamadas_catalogo == 1
    assert json.loads(cache.obter("catalogo_cripto_brl")) == ["BTC"]
    assert cache.ttls["catalogo_cripto_brl"] == 86400


def test_falha_ao_montar_o_catalogo_nao_grava_cache_e_propaga_na_cotacao():
    cache = FakeMercadoCache()
    roteador = _roteador(binance=FakeBinanceClient(indisponivel=True), cache=cache)

    with pytest.raises(BinanceIndisponivelError):
        roteador.buscar_cotacao_atual("BTC")

    assert cache.obter("catalogo_cripto_brl") is None


def test_historico_e_diario_e_sempre_verdadeiro_para_cripto_e_delega_para_acao():
    roteador = _roteador(binance=FakeBinanceClient(pares=["BTC"]))

    assert roteador.historico_e_diario("BTC", PeriodoHistorico.CINCO_ANOS) is True
    assert roteador.historico_e_diario("PETR4", PeriodoHistorico.CINCO_ANOS) is False
    assert roteador.historico_e_diario("PETR4", PeriodoHistorico.TRES_MESES) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/services/test_roteador_dados_mercado_service.py -q`
Expected: `ModuleNotFoundError: No module named 'app.services.roteador_dados_mercado_service'`.

- [ ] **Step 3: Write minimal implementation**

`src/app/services/roteador_dados_mercado_service.py`:

```python
from __future__ import annotations

import json
import logging

from app.domain.enums.periodo_historico import PeriodoHistorico
from app.domain.enums.tipo_ativo import TipoAtivo
from app.integrations.binance.client import BinanceClient, BinanceIndisponivelError
from app.integrations.brapi.client import AtivoEncontrado, CotacaoAtual, PontoHistorico
from app.services.dados_mercado_service import DadosMercadoService
from app.services.mercado_cache import MercadoCache

logger = logging.getLogger(__name__)

_CHAVE_CATALOGO = "catalogo_cripto_brl"


class RoteadorDadosMercadoService(DadosMercadoService):
    def __init__(
        self,
        brapi: DadosMercadoService,
        binance_client: BinanceClient,
        cache: MercadoCache,
        ttl_catalogo_segundos: int,
    ):
        self._brapi = brapi
        self._binance_client = binance_client
        self._cache = cache
        self._ttl_catalogo_segundos = ttl_catalogo_segundos

    def buscar_ativo(self, termo: str) -> list[AtivoEncontrado]:
        encontrados = self._brapi.buscar_ativo(termo)
        try:
            catalogo = self._catalogo()
        except BinanceIndisponivelError:
            logger.warning("Binance indisponivel; busca segue apenas com a brapi.")
            return encontrados

        termo_normalizado = termo.upper()
        return encontrados + [
            AtivoEncontrado(
                ticker=codigo,
                nome=codigo,
                tipo=TipoAtivo.CRIPTO,
                moeda="BRL",
                setor=None,
                fonte_dados="binance",
            )
            for codigo in catalogo
            if termo_normalizado in codigo
        ]

    def buscar_cotacao_atual(self, ticker: str) -> CotacaoAtual:
        if self._e_cripto(ticker):
            return self._binance_client.buscar_cotacao_atual(ticker)
        return self._brapi.buscar_cotacao_atual(ticker)

    def buscar_historico(self, ticker: str, periodo: PeriodoHistorico) -> list[PontoHistorico]:
        if self._e_cripto(ticker):
            return self._binance_client.buscar_historico(ticker, periodo)
        return self._brapi.buscar_historico(ticker, periodo)

    def historico_e_diario(self, ticker: str, periodo: PeriodoHistorico) -> bool:
        if self._e_cripto(ticker):
            return True
        return self._brapi.historico_e_diario(ticker, periodo)

    def _e_cripto(self, ticker: str) -> bool:
        return ticker in self._catalogo()

    def _catalogo(self) -> list[str]:
        em_cache = self._cache.obter(_CHAVE_CATALOGO)
        if em_cache is not None:
            return json.loads(em_cache)

        catalogo = self._binance_client.listar_pares_brl()
        self._cache.salvar(_CHAVE_CATALOGO, json.dumps(catalogo), self._ttl_catalogo_segundos)
        return catalogo
```

`src/app/core/config.py` — abaixo de `cache_ttl_cotacao_atual_segundos`, adicione `cache_ttl_catalogo_cripto_segundos: int = 86400`. `.env.example` — abaixo de `CACHE_TTL_COTACAO_ATUAL_SEGUNDOS=60`, adicione `CACHE_TTL_CATALOGO_CRIPTO_SEGUNDOS=86400`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit -q && .venv/bin/ruff check src tests`
Expected: todos passam.

- [ ] **Step 5: Commit**

```bash
git add src/app/services/roteador_dados_mercado_service.py src/app/core/config.py .env.example tests/fixtures/fake_binance_client.py tests/unit/services/test_roteador_dados_mercado_service.py
```

Mensagem: `feat(mercado): adiciona roteador brapi/Binance por ticker`

---

### Task 6: Montagem na API e no scheduler + verificação real

**Files:**
- Modify: `src/app/api/deps.py` (`get_dados_mercado_service`, novo `get_binance_client`)
- Modify: `src/app/scheduler/jobs.py` (`_executar_ciclo`, `_executar_indices_referencia`, `_executar_resumos_diarios`)
- Test: `tests/unit/api/test_deps.py`

**Interfaces:**
- Consumes: `BinanceClient` (Task 2), `RoteadorDadosMercadoService` (Task 5), `Settings.binance_base_url`, `Settings.cache_ttl_catalogo_cripto_segundos`.
- Produces: `get_binance_client(settings) -> BinanceClient`; `jobs._dados_mercado_service(settings: Settings, cache: MercadoCache) -> DadosMercadoService`.

- [ ] **Step 1: Write the failing test**

Em `tests/unit/api/test_deps.py`, adicione (sem tocar em rede: os clientes só fazem requisição quando chamados):

```python
def test_dados_mercado_service_envolve_o_roteador_no_cache():
    settings = Settings(_env_file=None)
    cache = FakeMercadoCache()

    service = get_dados_mercado_service(
        brapi_client=get_brapi_client(settings),
        binance_client=get_binance_client(settings),
        mercado_cache=cache,
        settings=settings,
    )

    assert isinstance(service, CachedDadosMercadoService)
    assert isinstance(service._interno, RoteadorDadosMercadoService)
```

com os imports `from app.api.deps import get_binance_client, get_brapi_client, get_dados_mercado_service`, `from app.core.config import Settings`, `from app.services.cached_dados_mercado_service import CachedDadosMercadoService`, `from app.services.roteador_dados_mercado_service import RoteadorDadosMercadoService`, `from tests.fixtures.fake_mercado_cache import FakeMercadoCache` (junte aos imports já existentes no arquivo).

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/api/test_deps.py -q`
Expected: `ImportError: cannot import name 'get_binance_client'`.

- [ ] **Step 3: Write minimal implementation**

`src/app/api/deps.py`:

```python
@lru_cache
def _binance_http_client(base_url: str) -> httpx.Client:
    return httpx.Client(base_url=base_url, timeout=10.0)


def get_binance_client(settings: Settings = Depends(get_settings)) -> BinanceClient:
    return BinanceClient(_binance_http_client(settings.binance_base_url))


def get_dados_mercado_service(
    brapi_client: BrapiClient = Depends(get_brapi_client),
    binance_client: BinanceClient = Depends(get_binance_client),
    mercado_cache: MercadoCache = Depends(get_mercado_cache),
    settings: Settings = Depends(get_settings),
) -> DadosMercadoService:
    return CachedDadosMercadoService(
        RoteadorDadosMercadoService(
            DadosMercadoService(brapi_client),
            binance_client,
            mercado_cache,
            ttl_catalogo_segundos=settings.cache_ttl_catalogo_cripto_segundos,
        ),
        mercado_cache,
        ttl_cotacao_atual=settings.cache_ttl_cotacao_atual_segundos,
    )
```

(substitui o `get_dados_mercado_service` atual; importe `BinanceClient` e `RoteadorDadosMercadoService`).

`src/app/scheduler/jobs.py` — adicione:

```python
@lru_cache
def _binance_http_client(base_url: str) -> httpx.Client:
    return httpx.Client(base_url=base_url, timeout=10.0)


def _dados_mercado_service(settings: Settings, cache: MercadoCache) -> DadosMercadoService:
    brapi_client = BrapiClient(
        _brapi_http_client(settings.brapi_base_url),
        settings.brapi_api_key or None,
    )
    return CachedDadosMercadoService(
        RoteadorDadosMercadoService(
            DadosMercadoService(brapi_client),
            BinanceClient(_binance_http_client(settings.binance_base_url)),
            cache,
            ttl_catalogo_segundos=settings.cache_ttl_catalogo_cripto_segundos,
        ),
        cache,
        ttl_cotacao_atual=settings.cache_ttl_cotacao_atual_segundos,
    )
```

e, em `_executar_ciclo`, `_executar_indices_referencia` e `_executar_resumos_diarios`, troque a montagem local de `brapi_client` + `CachedDadosMercadoService(DadosMercadoService(brapi_client), ...)` por `dados_mercado_service = _dados_mercado_service(settings, cache)` (onde `cache = RedisMercadoCache(_redis_client(settings.redis_url))`). Importe `BinanceClient`, `RoteadorDadosMercadoService` e `MercadoCache`; remova imports que ficarem sem uso.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit -q && .venv/bin/ruff check src tests`
Expected: todos passam.

- [ ] **Step 5: Verify against the real APIs**

Com `BRAPI_API_KEY` no `.env` e sem Redis/Postgres (cache e repositórios fake):

```bash
PYTHONPATH=src:. .venv/bin/python - <<'EOF'
import httpx
from uuid import uuid4
from app.core.config import get_settings
from app.domain.entities.ativo import Ativo
from app.domain.enums.periodo_historico import PeriodoHistorico as P
from app.domain.enums.tipo_ativo import TipoAtivo
from app.integrations.binance.client import BinanceClient
from app.integrations.brapi.client import BrapiClient
from app.services.ativo_service import AtivoService
from app.services.dados_mercado_service import DadosMercadoService
from app.services.roteador_dados_mercado_service import RoteadorDadosMercadoService
from tests.fixtures.fake_ativo_repository import FakeAtivoRepository
from tests.fixtures.fake_cotacao_repository import FakeCotacaoRepository
from tests.fixtures.fake_mercado_cache import FakeMercadoCache
s = get_settings()
r = RoteadorDadosMercadoService(
    DadosMercadoService(BrapiClient(httpx.Client(base_url=s.brapi_base_url, timeout=20), s.brapi_api_key or None)),
    BinanceClient(httpx.Client(base_url=s.binance_base_url, timeout=20)),
    FakeMercadoCache(), 86400,
)
print([(a.ticker, a.tipo.value, a.fonte_dados) for a in r.buscar_ativo("btc")][:5])
print("BTC", r.buscar_cotacao_atual("BTC").preco, "| WEGE3", r.buscar_cotacao_atual("WEGE3").preco)
ar, cr = FakeAtivoRepository(), FakeCotacaoRepository()
btc = Ativo(id=uuid4(), ticker="BTC", nome="BTC", tipo=TipoAtivo.CRIPTO, setor=None, moeda="BRL", fonte_dados="binance")
ar.salvar(btc)
AtivoService(ar, r, cr).atualizar_historico(btc.id, s.politica_historico())
c = cr.listar_por_ativo(btc.id)
print("BTC persistidas:", len(c), c[0].data_hora.date(), "->", c[-1].data_hora.date())
EOF
```

Expected: a busca lista `BTC` como `CRIPTO`/`binance`; preços de BTC (centenas de milhares) e WEGE3; ~1000 cotações de BTC persistidas, da data de ~2,7 anos atrás até hoje.

- [ ] **Step 6: Commit**

```bash
git add src/app/api/deps.py src/app/scheduler/jobs.py tests/unit/api/test_deps.py
```

Mensagem: `feat(binance): liga o roteador de dados de mercado na API e no scheduler`
