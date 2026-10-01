# PortfolioService — design

## Contexto

`Operacao` (`domain/entities/operacao.py`) e `TipoOperacao` já existem, mas só como dataclass — sem repository, sem tabela, sem service, sem controller. RF-10/11/12 (registro de operações, cálculo de rentabilidade, distribuição da carteira) e a vertical `PortfolioService` do modelo de classes não têm nenhuma implementação hoje.

Este sub-projeto fecha a vertical inteira de uma vez: CRUD de operações fictícias (RN-04 — nenhuma execução real em corretora) e as quatro consultas agregadas descritas no documento técnico (`posicoes`, `rentabilidade`, `comparativo_benchmark`, `distribuicao`).

**Decisões já tomadas em brainstorming, divergindo do documento técnico onde aplicável:**

- O documento define `rentabilidade(usuario, periodo)`. Esta vertical implementa `rentabilidade(usuario)` **sem** parâmetro de período — sempre "desde a 1ª operação". Considerar aportes/retiradas dentro de uma janela arbitrária sem distorcer o percentual exigiria retorno money-weighted (XIRR ou equivalente), fora de escopo para o MVP. `comparativo_benchmark` usa a mesma âncora (data da 1ª operação), o que mantém as duas consultas consistentes entre si.
- Preço médio ponderado (não FIFO) para apurar posição — mesmo método usado por corretoras brasileiras e pela Receita Federal, mais simples de auditar do que rastrear lotes individuais.
- CDI via série 12 do SGS/BCB (diária, composta), não a série 4390 (mensal acumulada) — permite ancorar em qualquer data exata.
- Ibovespa tratado como ticker comum (`^BVSP`) via `DadosMercadoService`, sem integração nova — confirmado que o brapi aceita ticker arbitrário nesse método.

**Fora do escopo desta vertical:**

- Retorno money-weighted / XIRR considerando aportes intermediários.
- Rate limit/backoff (RNF-06) em `BcbClient`/`DadosMercadoService` — `comparativo_benchmark` já tolera indisponibilidade (ver Erros), mas não reenfileira nem tenta de novo.
- FIFO ou qualquer outro método de custo além do preço médio ponderado.

## Arquitetura

```
src/app/domain/enums/tipo_benchmark.py           TipoBenchmark
src/app/domain/value_objects/posicao.py          Posicao
src/app/domain/value_objects/rentabilidade.py    Rentabilidade
src/app/domain/value_objects/comparativo.py      Comparativo
src/app/domain/value_objects/distribuicao.py     Distribuicao
src/app/repositories/interfaces/operacao_repository.py
src/app/repositories/sqlalchemy/operacao_repository.py
src/app/db/models/operacao.py
src/app/services/portfolio_service.py
src/app/api/v1/controllers/portfolio.py
src/app/api/v1/schemas/portfolio.py
```

`BcbClient` (`integrations/bcb/client.py`) ganha `buscar_serie_cdi(inicio: date, fim: date) -> list[PontoCdi]`, ao lado do já existente `buscar_ptax_venda`.

### Cálculo de posição (replay de operações)

Dado o histórico de `Operacao` de um `ativo_id` ordenado por `data` e, em caso de empate, por `criado_em` (mesmo cuidado de ordenação determinística já aplicado no scheduler):

```python
@dataclass
class _EstadoPosicao:
    quantidade: Decimal = Decimal(0)
    preco_medio: Decimal = Decimal(0)
    lucro_realizado: Decimal = Decimal(0)

def _replay(operacoes: list[Operacao]) -> _EstadoPosicao:
    estado = _EstadoPosicao()
    for op in sorted(operacoes, key=lambda o: (o.data, o.criado_em)):
        if op.tipo == TipoOperacao.COMPRA:
            custo_total = estado.quantidade * estado.preco_medio + op.valor_total()
            estado.quantidade += op.quantidade
            estado.preco_medio = custo_total / estado.quantidade
        else:  # VENDA
            if op.quantidade > estado.quantidade:
                raise QuantidadeInsuficienteError(op.ativo_id)
            estado.lucro_realizado += (op.preco_unitario - estado.preco_medio) * op.quantidade
            estado.quantidade -= op.quantidade
            if estado.quantidade == 0:
                estado.preco_medio = Decimal(0)
    return estado
```

Venda nunca altera `preco_medio` da quantidade remanescente; zerar a posição reseta `preco_medio` para que uma compra futura não herde a média antiga. `lucro_realizado` é acumulado à parte e nunca entra no cálculo de rentabilidade da posição aberta.

### `Posicao` (`domain/value_objects/posicao.py`)

```python
@dataclass
class Posicao:
    ativo_id: UUID
    ticker: str
    quantidade: Decimal
    preco_medio: Decimal
    cotacao_atual: Decimal
    valor_mercado: Decimal
    valor_mercado_brl: Decimal
    lucro_nao_realizado: Decimal
    lucro_realizado: Decimal
```

`PortfolioService.posicoes(usuario_id)`: agrupa `OperacaoRepository.listar_por_usuario(usuario_id)` por `ativo_id`, descarta ativos com `quantidade == 0` após o replay, busca `Ativo` (ticker/moeda) e `cotacao_atual` via `DadosMercadoService.buscar_cotacao_atual(ativo.ticker)` para cada um, e converte para BRL via `CambioService.converter(valor, de=ativo.moeda, para="BRL")` só no campo `valor_mercado_brl` — os demais campos ficam na moeda original do ativo.

### `Rentabilidade` (`domain/value_objects/rentabilidade.py`)

```python
@dataclass
class Rentabilidade:
    custo_base_brl: Decimal
    valor_mercado_brl: Decimal
    lucro_nao_realizado_brl: Decimal
    lucro_realizado_brl: Decimal
    percentual: Decimal  # lucro_nao_realizado_brl / custo_base_brl; Decimal(0) se custo_base_brl == 0
```

`posicoes()` e `rentabilidade()` compartilham um helper privado `_replay_por_ativo(usuario_id) -> dict[UUID, _EstadoPosicao]` que roda o replay para **todo** `ativo_id` já operado pelo usuário, inclusive os zerados. A partir daí:
- `posicoes()` descarta as entradas com `quantidade == 0` (nada a mostrar como posição aberta) e só então busca `Ativo`/cotação para as remanescentes.
- `rentabilidade()` itera o dict inteiro sem filtrar: `custo_base_brl` e `valor_mercado_brl` somam `quantidade * preco_medio` e `quantidade * cotacao_atual` (ambos zero para ativos já zerados, então não exigem buscar cotação); `lucro_realizado_brl` soma `lucro_realizado` de todas as entradas, incluindo as zeradas — é o único jeito de refletir o lucro de um ativo totalmente vendido.

### `Comparativo` (`domain/value_objects/comparativo.py`)

```python
@dataclass
class Comparativo:
    benchmark: TipoBenchmark
    rentabilidade_carteira_percentual: Decimal
    rentabilidade_benchmark_percentual: Decimal | None  # None se benchmark indisponivel
```

`PortfolioService.comparativo_benchmark(usuario_id, benchmark)`:
1. `data_inicio` = menor `data` entre todas as `Operacao` do usuário; se não houver nenhuma operação, levanta `PortfolioVazioError`.
2. `rentabilidade_carteira_percentual` = `percentual` de `rentabilidade(usuario_id)`.
3. Para `TipoBenchmark.CDI`: `pontos = bcb_client.buscar_serie_cdi(data_inicio, hoje)`, taxa acumulada = `math.prod(1 + p.valor / 100 for p in pontos) - 1`. Captura `BcbIndisponivelError` → `rentabilidade_benchmark_percentual = None`.
4. Para `TipoBenchmark.IBOVESPA`: `pontos = dados_mercado_service.buscar_historico("^BVSP", periodo_correspondente)` — chamado direto no `DadosMercadoService`/`CachedDadosMercadoService`, **nunca** via `AtivoService.historico`, que persiste candles diários em `cotacoes` via `CotacaoRepository.salvar_muitas` (misturaria granularidade de índice com a de ativos negociáveis — mesmo problema já corrigido antes para cotações). Retorno percentual = `(fechamento[-1] - fechamento[0]) / fechamento[0]`. Captura `BrapiIndisponivelError`/`TickerNaoEncontradoError` → `None`.

`periodo_correspondente` mapeia `data_inicio` para o `PeriodoHistorico` existente mais próximo que cobre o intervalo (ex.: mais de 1 ano → `PeriodoHistorico.CINCO_ANOS`); não é uma correspondência exata a `data_inicio`, é uma limitação aceita do enum existente — registrado aqui para não ser lido como bug.

### `Distribuicao` (`domain/value_objects/distribuicao.py`)

```python
@dataclass
class Distribuicao:
    por_classe: dict[TipoAtivo, Decimal]   # percentual, cada dict soma 1.0
    por_setor: dict[str, Decimal]          # percentual
    por_moeda: dict[str, Decimal]          # percentual, chave = moeda original do ativo
```

`PortfolioService.distribuicao(usuario_id)`: usa as mesmas posições de `posicoes(usuario_id)`. RF-12 pede "composição **percentual**" nas três quebras — as três dividem `valor_mercado_brl` da posição pelo total em BRL da carteira (não dá pra somar BRL com USD sem converter, então a base comum é sempre BRL; o que muda entre as quebras é só a chave de agrupamento). `por_classe` agrupa por `ativo.tipo`; `por_setor` agrupa por `ativo.setor`, e ativos sem setor (`Ativo.setor is None` — o caso de cripto, ver `domain/entities/ativo.py`) entram sob a chave literal `"N/A"`, nunca omitidos do total; `por_moeda` agrupa pela moeda original do ativo (`ativo.moeda`) — a moeda em si é só o rótulo do grupo, o valor usado no cálculo já está convertido para BRL como nos outros dois.

### `TipoBenchmark` (`domain/enums/tipo_benchmark.py`)

```python
class TipoBenchmark(str, Enum):
    CDI = "CDI"
    IBOVESPA = "IBOVESPA"
```

## `OperacaoRepository` (interface + SQLAlchemy + Fake)

```python
class OperacaoRepository(ABC):
    def salvar(self, operacao: Operacao) -> None: ...
    def buscar_por_id(self, operacao_id: UUID) -> Operacao | None: ...
    def listar_por_usuario(self, usuario_id: UUID) -> list[Operacao]: ...
    def remover(self, operacao: Operacao) -> None: ...
```

Tabela `operacoes`: `id, usuario_id (FK usuarios), ativo_id (FK ativos), tipo (String), quantidade (Numeric), preco_unitario (Numeric), data (Date), criado_em (DateTime)`. Migration encadeia a partir da head atual `12b09b3cdf77`.

`FakeOperacaoRepository` (`tests/fixtures/`) segue o mesmo padrão de `FakeAlertaRepository`: dict em memória por `id`, `listar_por_usuario` filtra por `usuario_id`.

## `PortfolioService` (`services/portfolio_service.py`)

```python
class PortfolioService:
    def __init__(
        self,
        operacao_repository: OperacaoRepository,
        ativo_repository: AtivoRepository,
        dados_mercado_service: DadosMercadoService,
        cambio_service: CambioService,
        bcb_client: BcbClient,
    ): ...

    def registrar_operacao(
        self, usuario_id: UUID, ativo_id: UUID, tipo: TipoOperacao,
        quantidade: Decimal, preco_unitario: Decimal, data: date,
    ) -> Operacao: ...
    def listar_operacoes(self, usuario_id: UUID) -> list[Operacao]: ...
    def remover_operacao(self, usuario_id: UUID, operacao_id: UUID) -> None: ...
    def posicoes(self, usuario_id: UUID) -> list[Posicao]: ...
    def rentabilidade(self, usuario_id: UUID) -> Rentabilidade: ...
    def comparativo_benchmark(self, usuario_id: UUID, benchmark: TipoBenchmark) -> Comparativo: ...
    def distribuicao(self, usuario_id: UUID) -> Distribuicao: ...
```

`registrar_operacao` valida (`OperacaoInvalidaError`): `quantidade > 0`, `preco_unitario > 0`, `data <= date.today()`; busca `Ativo` via `AtivoRepository.buscar_por_id` (`AtivoNaoEncontradoError`, já existe, mesmo padrão de `AlertaService`); se `tipo == VENDA`, faz o replay das operações já registradas do ativo e levanta `QuantidadeInsuficienteError` se `quantidade` pedida excede a posição atual antes de persistir. `remover_operacao`/`listar_operacoes` seguem o padrão RN-09 de `AlertaService._buscar_alerta` (`OperacaoNaoEncontradaError` se `usuario_id` não bate).

## Controller (`api/v1/controllers/portfolio.py`)

```
POST   /api/v1/operacoes
GET    /api/v1/operacoes
DELETE /api/v1/operacoes/{operacao_id}
GET    /api/v1/portfolio/posicoes
GET    /api/v1/portfolio/rentabilidade
GET    /api/v1/portfolio/benchmark?benchmark=CDI|IBOVESPA
GET    /api/v1/portfolio/distribuicao
```

Todos autenticados via `get_usuario_atual` (`deps.py`), mesmo padrão de `alertas.py`. `api/deps.py` ganha `get_operacao_repository`, `get_portfolio_service`.

## Erros

| Erro | Onde | Quando |
|---|---|---|
| `OperacaoInvalidaError` | `services/exceptions.py` | `quantidade`/`preco_unitario` <= 0, ou `data` futura |
| `QuantidadeInsuficienteError` | `services/exceptions.py` | venda que excede a quantidade em posição |
| `OperacaoNaoEncontradaError` | `services/exceptions.py` | remoção/consulta de operação inexistente ou de outro usuário (RN-09) |
| `PortfolioVazioError` | `services/exceptions.py` | `comparativo_benchmark` sem nenhuma operação registrada |

`comparativo_benchmark` não propaga `BcbIndisponivelError`/`BrapiIndisponivelError`/`TickerNaoEncontradoError` — retorna `Comparativo` com `rentabilidade_benchmark_percentual=None`, mesmo espírito do fallback do UC-03 para IA indisponível e do tratamento de `BcbIndisponivelError` já existente em `AlertaService.avaliar_alertas`. `posicoes`/`distribuicao` fazem uma chamada de cotação por ativo em carteira; se uma falhar (`BrapiIndisponivelError`), o ativo é omitido do resultado e um `warning` é logado — não derruba a consulta inteira.

## Testes

- `tests/unit/services/test_portfolio_service.py` — o núcleo desta vertical:
  - Replay de preço médio: compra única; compras múltiplas (média ponderada correta); compra + venda parcial (média não muda); venda total zera `quantidade` e reseta `preco_medio`; compra após zerar não herda média antiga; duas operações na mesma `data` respeitam `criado_em` como desempate.
  - `registrar_operacao`: rejeita `quantidade`/`preco_unitario` <= 0; rejeita `data` futura; rejeita venda que excede posição (`QuantidadeInsuficienteError`) sem persistir a operação inválida.
  - `rentabilidade`: `lucro_nao_realizado` e `lucro_realizado` calculados e reportados separadamente; `percentual` não estoura quando há venda parcial lucrativa (o caso que quebraria a fórmula ingênua baseada em custo líquido); `percentual = 0` quando `custo_base_brl == 0` (posição zerada).
  - `distribuicao`: `por_classe`/`por_setor` somam 1.0 em BRL; `por_moeda` reporta valores na moeda original, não convertidos.
  - `comparativo_benchmark`: CDI composto corretamente a partir de múltiplos pontos diários; Ibovespa via `buscar_historico("^BVSP", ...)`; `PortfolioVazioError` sem operações; `rentabilidade_benchmark_percentual=None` quando `BcbIndisponivelError`/`BrapiIndisponivelError`.
  - Isolamento RN-09: usuário A não lista, remove ou vê nas consultas agregadas operação de usuário B — mesmo padrão do teste de isolamento já existente para alertas.
- `tests/integration/repositories/test_operacao_repository.py` — salvar/buscar/listar/remover contra Postgres real, isolamento entre usuários.
- `tests/unit/integrations/bcb/test_client.py` — `buscar_serie_cdi` com `httpx.MockTransport`, mesmo padrão já usado para `buscar_ptax_venda` nesse arquivo (não há teste de integração contra o BCB real no projeto; `buscar_ptax_venda` também só tem unit test mockado). Formato de data e estrutura de resposta já validados manualmente durante o brainstorming (`dataInicial`/`dataFinal` em `dd/MM/yyyy`, resposta `[{"data": "dd/MM/yyyy", "valor": "0.051660"}, ...]`, só dias úteis) — o mock replica esse formato exato.
