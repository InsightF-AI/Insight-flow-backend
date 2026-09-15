# IndicadorService — Design

Data: 2026-09-10
Branch: `feature/indicador-service`
Item do roadmap: #3 (RF-06)

## Contexto

`cotacoes` agora persiste só candles diários (fix `fix/cotacoes-granularidade`, mergeado em `develop`). Existe uma série diária limpa por ativo via `CotacaoRepository.listar_por_ativo(ativo_id)`. A entidade de domínio `IndicadorTecnico` já existe (`src/app/domain/entities/indicador_tecnico.py`) mas sem model, repository, service ou controller.

RF-06 pede cálculo automático de SMA(20,50,200), RSI(14), MACD(12,26,9), Bandas de Bollinger(20,2) e volume relativo, "para todo ativo em watchlist ativa". O Scheduler (APScheduler) que dispararia isso automaticamente ainda não existe — é um item mais à frente no roadmap. Este item entrega o motor de cálculo, a persistência e um endpoint de consulta que dispara o cálculo sob demanda, seguindo o mesmo padrão que `/historico` já usa (computa e persiste na hora da requisição).

`pandas-ta` já está no `requirements.txt` e testado funcionando (`ta.sma` retorna série correta sobre um DataFrame).

## Decisões já validadas com o usuário

1. **Escopo**: motor de cálculo + persistência + endpoint de consulta (não só motor+persistência).
2. **Histórico insuficiente**: pula o indicador silenciosamente (ex: `SMA(200)` com 50 cotações disponíveis não aparece na resposta; os demais indicadores calculáveis aparecem normalmente). Não lança erro.
3. **Estratégia de persistência**: só o valor mais recente por `(ativo_id, tipo, parâmetros)` — upsert, sem manter série histórica de cada cálculo. `SinalService` (item futuro) vai consumir o valor mais recente; `RF-08` (backtest) recalcula historicamente a partir de `cotacoes`, não lê indicadores históricos persistidos.

## Componentes

### `IndicadorTecnicoModel` (`src/app/db/models/indicador_tecnico.py`)

| Coluna | Tipo | Observação |
|---|---|---|
| `id` | UUID, PK | |
| `ativo_id` | UUID, FK → `ativos.id` | |
| `tipo` | String(20) | valor de `TipoIndicador` |
| `parametros` | JSON | dict cru, ex: `{"periodo": 20}` |
| `chave` | String(50) | derivada de `tipo`+`parametros` na camada de persistência, ex: `"SMA_20"`, `"MACD_12_26_9"`. **Não existe na entidade de domínio** — é um detalhe do repositório, calculado no momento de salvar. |
| `data_calculo` | DateTime(timezone=True) | |
| `valor` | Numeric(18,6) | |
| `valores_auxiliares` | JSON, nullable | |

Constraint única: `UNIQUE(ativo_id, chave)`. Migration Alembic nova, seguindo o padrão das migrations existentes (`cria_tabela_cotacoes` etc.).

`parametros` por tipo de indicador (dict construído sempre na mesma ordem de chaves, pra `chave` ser determinística):

| Tipo | `parametros` |
|---|---|
| SMA | `{"periodo": N}` (N = 20, 50 ou 200) |
| RSI | `{"periodo": 14}` |
| MACD | `{"rapida": 12, "lenta": 26, "sinal": 9}` |
| Bollinger | `{"periodo": 20, "desvios": 2}` |
| Volume Relativo | `{"periodo": 20}` |

`chave = f"{tipo.value}_" + "_".join(str(v) for v in parametros.values())` — ex: `"SMA_20"`, `"MACD_12_26_9"`, `"BOLLINGER_20_2"`.

### `IndicadorTecnicoRepository` (interface + impl SQLAlchemy)

Espelha `CotacaoRepository`:

```python
class IndicadorTecnicoRepository(ABC):
    def salvar(self, indicador: IndicadorTecnico) -> None: ...
    def listar_por_ativo(self, ativo_id: UUID) -> list[IndicadorTecnico]: ...
```

`salvar` faz upsert via `INSERT ... ON CONFLICT (ativo_id, chave) DO UPDATE`, computando `chave` a partir de `indicador.tipo` + `indicador.parametros` (função pura, ex: `f"{tipo.value}_{'_'.join(str(v) for v in parametros.values())}"`).

### `IndicadorService` (`src/app/services/indicador_service.py`)

Dependências: `CotacaoRepository`, `IndicadorTecnicoRepository`, `AtivoRepository`.

**Métodos de cálculo puros** (sem acesso a repositório, testáveis com listas fixas de `Cotacao`):

```python
def calcular_sma(cotacoes: list[Cotacao], periodo: int) -> IndicadorTecnico | None
def calcular_rsi(cotacoes: list[Cotacao], periodo: int) -> IndicadorTecnico | None
def calcular_macd(cotacoes: list[Cotacao], rapida=12, lenta=26, sinal=9) -> IndicadorTecnico | None
def calcular_bollinger(cotacoes: list[Cotacao], periodo: int, desvios: float) -> IndicadorTecnico | None
def calcular_volume_relativo(cotacoes: list[Cotacao], periodo: int) -> IndicadorTecnico | None
```

Cada um: monta um `pandas.DataFrame` a partir de `cotacoes` (colunas `close`/`high`/`low`/`volume` conforme o indicador), chama a função correspondente do `pandas-ta`, pega o último valor da série resultante. Se o último valor for `NaN` (histórico insuficiente para aquele período) **ou se `cotacoes` estiver vazia**, retorna `None` — nenhum dos métodos lança exceção por falta de dado, só por erro de fato inesperado. Caso contrário, monta e retorna um `IndicadorTecnico` com `id` novo (`uuid4()`), `data_calculo=datetime.now(UTC)`.

Mapeamento `valor`/`valores_auxiliares`:
- SMA, RSI, Volume Relativo: só `valor`.
- MACD: `valor` = linha MACD; `valores_auxiliares = {"linha_sinal": ..., "histograma": ...}`.
- Bollinger: `valor` = banda média; `valores_auxiliares = {"banda_superior": ..., "banda_inferior": ...}`.

**Orquestração**:

```python
def calcular_todos(self, ativo_id: UUID) -> list[IndicadorTecnico]:
    ativo = self._buscar_ativo(ativo_id)  # AtivoNaoEncontradoError se nao existir
    cotacoes = self._cotacao_repository.listar_por_ativo(ativo.id)
    candidatos = [
        self.calcular_sma(cotacoes, 20), self.calcular_sma(cotacoes, 50), self.calcular_sma(cotacoes, 200),
        self.calcular_rsi(cotacoes, 14),
        self.calcular_macd(cotacoes),
        self.calcular_bollinger(cotacoes, 20, 2),
        self.calcular_volume_relativo(cotacoes, 20),
    ]
    calculados = [c for c in candidatos if c is not None]
    for indicador in calculados:
        self._indicador_repository.salvar(indicador)
    return calculados
```

Nota de consistência: a doc técnica mostra `calcular_todos(ativo)` recebendo o objeto `Ativo` no diagrama de classes UML. Este design usa `ativo_id: UUID` no método público, resolvendo o `Ativo` internamente (mesmo padrão de `AtivoService`/`WatchlistService` já existentes no código) — prioriza consistência com o restante do codebase sobre o diagrama UML literal.

### Endpoint

`GET /ativos/{ativo_id}/indicadores` em `src/app/api/v1/controllers/ativos.py`, seguindo o padrão de `/cotacao` e `/historico`: chama `indicador_service.calcular_todos(ativo_id)` (calcula e persiste na hora da requisição), retorna a lista serializada. 404 (`AtivoNaoEncontradoError`) se o ativo não existir. Novo schema de resposta `IndicadorTecnicoResponse` em `src/app/api/v1/schemas/indicador.py`.

Wiring em `api/deps.py`: `get_indicador_tecnico_repository`, `get_indicador_service` (compondo `AtivoRepository` + `CotacaoRepository` + `IndicadorTecnicoRepository`), seguindo o padrão de `get_ativo_service`.

## Erros

Reutiliza `AtivoNaoEncontradoError` já existente (`services/exceptions.py`) para ativo inexistente. Nenhum erro novo necessário — histórico insuficiente não é erro, é ausência silenciosa do indicador no resultado.

## Testes

- **Unitário dos 5 métodos de cálculo**: listas de `Cotacao` fixas (sintéticas, sem fake de repositório) cobrindo caso normal (retorna `IndicadorTecnico` com valor esperado) e histórico insuficiente (retorna `None`).
- **Unitário do `calcular_todos`**: `FakeCotacaoRepository` + `FakeIndicadorTecnicoRepository` (novo fixture) + `FakeAtivoRepository` já existente — verifica que os indicadores calculáveis são persistidos e os não-calculáveis são omitidos; `AtivoNaoEncontradoError` para ativo inexistente.
- **Integração do `IndicadorTecnicoRepository`**: contra Postgres real (`tests/integration/repositories/test_indicador_tecnico_repository.py`) — upsert por `(ativo_id, chave)`, não duplica em recálculo.
- **Teste do endpoint**: `tests/unit/api/test_indicador_controller.py` (ou adicionado a `test_cotacao_controller.py`/novo arquivo) — 200 com indicadores calculados, 404 para ativo inexistente.

## Fora de escopo (explicitamente)

- Disparo automático via Scheduler (item futuro do roadmap).
- `SinalService` / avaliação de regras sobre os indicadores (RF-07, item futuro).
- Qualquer mudança em `cotacoes` ou no fluxo de persistência de histórico (já resolvido em `fix/cotacoes-granularidade`).
