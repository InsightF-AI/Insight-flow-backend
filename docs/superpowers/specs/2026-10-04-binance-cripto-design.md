# Binance (criptomoedas) — design

## Contexto

A auditoria ERS x código de 2026-10-04 mostrou que criptomoedas não funcionam em nenhum ponto do sistema:

- `src/app/integrations/binance/` só tem um `__init__.py` vazio.
- `_MAPA_SUBTYPE` do `BrapiClient` descarta tudo que não é stock/fii/etf/bdr, então a busca nunca devolve cripto e não dá para adicionar BTC à watchlist.
- O job `ciclo_cripto` (5 em 5 minutos, RN-06) roda sem nenhum ativo para processar.
- O plano gratuito da brapi, usado pelo projeto, recusa `/api/v2/crypto` (403, exige plano Startup).

Requisitos afetados: RF-04, RF-05, RF-06, RF-07, RF-08 e RF-18 para cripto; RN-06 (reavaliação a cada 5 minutos para cripto). A ERS (seção 8) já prevê a Binance como fonte de dados de cripto.

A API pública da Binance foi testada em 2026-10-04 sem chave:

- `/api/v3/ticker/24hr?symbol=BTCBRL` → 200 (peso 2).
- `/api/v3/klines?symbol=BTCBRL&interval=1d&limit=1000` → 200, 1000 candles diários (~2,7 anos), peso 6.
- `/api/v3/exchangeInfo` → 18 pares com `quoteAsset=BRL` e `status=TRADING`: BTC, USDT, ETH, BNB, XRP, LINK, LTC, DOGE, ADA, SHIB, SOL, AVAX, PEPE, NEAR, RENDER, POL, SUI, USDC.

## Decisões

1. **Cotação em BRL** (pares `XXXBRL`). Ativos cripto têm `moeda="BRL"`; alertas e carteira não precisam de câmbio. Isso substitui a premissa antiga do `CambioService` ("cripto em USD via Binance"), que continua válido para ativos USD que vierem a existir.
2. **Roteamento por ticker** (abordagem A). Um `RoteadorDadosMercadoService` implementa a interface `DadosMercadoService` e decide a fonte pelo ticker: se está no catálogo de pares BRL da Binance, vai para a Binance; senão, para a brapi. Os serviços consumidores não mudam. Tickers da B3 sempre têm dígito e os códigos de cripto não, então não há colisão prática.
3. **Histórico profundo para cripto.** A coleta inicial de cripto busca 5A, que na Binance vira 1000 candles diários. Isso habilita SMA 200 e o backtest de 24 meses (RF-06, RF-08, RN-03) para cripto. Ações continuam com 3M por causa do plano gratuito da brapi.

Fora do escopo: pares USDT, WebSocket de preço em tempo real e nomes completos das criptos ("Bitcoin"); o nome do ativo cripto é o próprio código.

## Componentes

### 1. Erros neutros — `src/app/integrations/erros.py`

```python
class FonteDadosIndisponivelError(Exception): ...
class TickerNaoEncontradoError(Exception): ...
```

- `BrapiIndisponivelError(FonteDadosIndisponivelError)` continua em `integrations/brapi/client.py`.
- Novo `BinanceIndisponivelError(FonteDadosIndisponivelError)` em `integrations/binance/client.py`.
- `TickerNaoEncontradoError` sai de `integrations/brapi/client.py` e passa a ser importado de `integrations/erros.py` por todos (brapi, binance, services, controllers, fakes, testes).
- Todo ponto em `src/` que captura `BrapiIndisponivelError` passa a capturar `FonteDadosIndisponivelError`. Assim uma falha da Binance responde 503, como a da brapi, e não 500.

### 2. `BinanceClient` — `src/app/integrations/binance/client.py`

```python
class BinanceClient:
    def __init__(self, http_client: httpx.Client): ...
    def listar_pares_brl(self) -> list[str]: ...
    def buscar_cotacao_atual(self, ticker: str) -> CotacaoAtual: ...
    def buscar_historico(self, ticker: str, periodo: PeriodoHistorico) -> list[PontoHistorico]: ...
```

- Base URL configurável (`binance_base_url`, padrão `https://api.binance.com`), sem chave.
- `listar_pares_brl`: `GET /api/v3/exchangeInfo`, devolve `baseAsset` dos símbolos com `quoteAsset == "BRL"` e `status == "TRADING"`.
- `buscar_cotacao_atual`: `GET /api/v3/ticker/24hr?symbol={ticker}BRL`. Mapeamento: `preco=lastPrice`, `variacao=priceChange`, `variacao_percentual=priceChangePercent`, `maxima_dia=highPrice`, `minima_dia=lowPrice`, `abertura=openPrice`, `volume=volume` (quantidade negociada, mesma semântica da brapi). `ticker` do resultado é o código sem o sufixo (`BTC`).
- `buscar_historico`: `GET /api/v3/klines?symbol={ticker}BRL&interval=1d&limit=N`, com `N` = 7 (1S), 30 (1M), 90 (3M), 365 (1A), 1000 (5A); 1D usa 1 (o `AtivoService` não chama histórico para 1D, mas o cliente cobre o enum inteiro). Cada kline vira `PontoHistorico(data=openTime em UTC, abertura, maxima, minima, fechamento, volume)`, ordenado do mais antigo para o mais recente.
- Erros: HTTP 400 com corpo `{"code": -1121}` (símbolo inválido) → `TickerNaoEncontradoError`; qualquer outro status de erro ou `httpx.HTTPError` → `BinanceIndisponivelError`.

### 3. `RoteadorDadosMercadoService` — `src/app/services/roteador_dados_mercado_service.py`

```python
class RoteadorDadosMercadoService(DadosMercadoService):
    def __init__(
        self,
        brapi: DadosMercadoService,
        binance_client: BinanceClient,
        cache: MercadoCache,
        ttl_catalogo_segundos: int,
    ): ...
```

- Catálogo de cripto: `listar_pares_brl()` guardado no `MercadoCache` sob a chave `catalogo_cripto_brl` (JSON de lista) por `ttl_catalogo_segundos` (config `cache_ttl_catalogo_cripto_segundos`, padrão 86400).
- `buscar_cotacao_atual(ticker)` e `buscar_historico(ticker, periodo)`: ticker no catálogo → Binance; senão → brapi.
- `buscar_ativo(termo)`: resultados da brapi + criptos do catálogo cujo código contém o termo (sem diferenciar maiúsculas), como `AtivoEncontrado(ticker=codigo, nome=codigo, tipo=CRIPTO, moeda="BRL", setor=None, fonte_dados="binance")`. Se a Binance falhar ao montar o catálogo, a busca segue só com a brapi (registra um aviso no log). Se a brapi falhar, o erro propaga, como hoje.
- Se a Binance falhar ao montar o catálogo dentro de cotação ou histórico, o erro propaga como `BinanceIndisponivelError`: sem catálogo não dá para saber a fonte, e mandar cripto para a brapi geraria um "ticker não encontrado" enganoso.
- `historico_e_diario(ticker, periodo)`: `True` para cripto; delega à brapi para os demais.

Montagem em `deps.py` (`get_dados_mercado_service`) e em `jobs.py`: `CachedDadosMercadoService(RoteadorDadosMercadoService(DadosMercadoService(brapi_client), binance_client, cache, ttl), cache, ttl)`. O `httpx.Client` da Binance usa `lru_cache`, como o da brapi.

### 4. Histórico diário decidido pela fonte

`DadosMercadoService` ganha `historico_e_diario(ticker: str, periodo: PeriodoHistorico) -> bool`:

- `DadosMercadoService` (brapi): `intervalo_de(periodo) == INTERVALO_DIARIO`.
- `CachedDadosMercadoService`: delega ao serviço interno.
- `RoteadorDadosMercadoService`: ver acima.
- `FakeDadosMercadoService`: regra da brapi, mais um parâmetro `tickers_diarios: set[str]` que força `True`.

`AtivoService._coletar_historico` troca `intervalo_de(periodo) == INTERVALO_DIARIO` por `self._dados_mercado_service.historico_e_diario(ativo.ticker, periodo)`.

### 5. Política de histórico por tipo de ativo

```python
@dataclass(frozen=True)
class PoliticaHistorico:
    periodo_backfill: PeriodoHistorico
    periodo_backfill_cripto: PeriodoHistorico
    minimo_cotacoes: int

    def periodo_backfill_de(self, tipo: TipoAtivo) -> PeriodoHistorico: ...
```

- Fica em `src/app/domain/value_objects/politica_historico.py`.
- Substitui o par `(periodo_backfill, minimo_cotacoes)` em `AtivoService.atualizar_historico`, `WatchlistService.__init__`, `executar_ciclo_monitoramento` / `_processar_ativo` e `atualizar_indices_referencia`.
- `AtivoService.atualizar_historico(ativo_id, politica)` usa `politica.periodo_backfill_de(ativo.tipo)` quando há menos de `minimo_cotacoes` cotações salvas; senão continua com `UM_MES`.
- Config nova: `historico_backfill_periodo_cripto: PeriodoHistorico = CINCO_ANOS` (`HISTORICO_BACKFILL_PERIODO_CRIPTO=5A` no `.env.example`). `Settings` ganha uma propriedade ou função que monta a `PoliticaHistorico`, usada por `deps.py` e `jobs.py`.

### 6. Origem do ativo

- `AtivoEncontrado` ganha `fonte_dados: str = "brapi"` (último campo, com padrão; os usos existentes não mudam).
- `WatchlistService._resolver_ativo_na_brapi` passa a se chamar `_resolver_ativo` e usa `correspondente.fonte_dados` em vez do `"brapi"` fixo.
- `AtivoEncontradoResponse` não muda (não expõe a fonte).

## Fluxo de cripto ponta a ponta

1. `GET /ativos/buscar?termo=btc` devolve `BTC` (CRIPTO, BRL) junto com os resultados da brapi.
2. `POST /watchlist {"ticker": "BTC"}` resolve pelo roteador, salva o `Ativo` com `fonte_dados="binance"` e dispara a coleta inicial de 5A (1000 candles gravados).
3. `ciclo_cripto` (5 min) passa a encontrar BTC: cotação pela Binance (com cache de 60s), avaliação de alertas, atualização de 1M de histórico, indicadores e sinais.
4. `GET /ativos/{id}/historico?periodo=1A` lê do banco; `/indicadores` já tem SMA 200; `/sinais/{regra}/backtest` cobre 24 meses.

## Testes

Todos unitários e sem rede, no padrão TDD do projeto.

- `tests/unit/integrations/binance/test_client.py` (`httpx.MockTransport`): catálogo filtra BRL + TRADING; cotação mapeia o ticker 24h e remove o sufixo; klines usam o `limit` por período e saem ordenados; `-1121` → `TickerNaoEncontradoError`; 500 e erro de rede → `BinanceIndisponivelError`.
- `tests/unit/services/test_roteador_dados_mercado_service.py` (fakes para brapi, Binance e cache): cripto vai para a Binance e ação para a brapi; busca junta as fontes; busca segue com a Binance fora; catálogo vem do cache sem nova chamada; catálogo é gravado com o TTL configurado; `historico_e_diario` por fonte.
- `tests/unit/services/test_ativo_service.py`: cripto com poucas cotações busca 5A e grava; ação continua em 3M; período não diário não é gravado.
- `tests/unit/services/test_watchlist_service.py`: ativo vindo da Binance é salvo com `fonte_dados="binance"`.
- `tests/unit/scheduler/test_ciclo.py`: BTC na watchlist com tipo CRIPTO é processado pelo ciclo de cripto e dispara alerta.
- `tests/unit/api/test_cotacao_controller.py`: `BinanceIndisponivelError` vira 503.
- Testes existentes que importam `TickerNaoEncontradoError` do módulo da brapi passam a importar de `integrations/erros.py`.

Um `FakeBinanceClient` em `tests/fixtures/` dá suporte aos testes do roteador.

## Riscos

- **Bloqueio regional da Binance.** `api.binance.com` responde do Brasil (testado), mas é bloqueado em algumas regiões (ex.: EUA). Se o servidor de produção estiver numa região bloqueada, a base URL configurável permite trocar para um espelho (`data-api.binance.vision`).
- **Limites de uso.** O limite é 6000 de peso por minuto por IP. Um ciclo de cripto com N ativos custa cerca de 8N de peso a cada 5 minutos (ticker 24h + klines de 1M), bem abaixo do limite.
- **Candle do dia em aberto.** O último kline é o dia corrente, ainda em aberto, igual ao comportamento da brapi; o upsert por `(ativo_id, data_hora)` atualiza esse candle a cada ciclo.
