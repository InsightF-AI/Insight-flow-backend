# SinalService — Design

Data: 2026-09-10
Branch: `feature/sinal-service`
Item do roadmap: #4 (RF-07, RF-08)

## Contexto

`IndicadorService` (item 3, mergeado em `develop`) calcula e persiste indicadores técnicos em `indicadores_tecnicos`, upsert por `(ativo_id, chave)` — **só o valor mais recente de cada indicador**, sem histórico de cálculos. `cotacoes` persiste só candles diários, com histórico completo.

RF-07 pede detecção contínua de sinais técnicos (regras avaliadas sobre os indicadores, ativação/desativação persistida). RF-08 pede, pra cada sinal, o histórico das ocorrências da mesma condição nos últimos 24 meses com retorno médio em janelas de 5, 20 e 60 pregões (RN-03). O Scheduler que dispararia a avaliação automaticamente ainda não existe — esse item entrega o motor + persistência + endpoints de consulta sob demanda, seguindo o mesmo padrão do `IndicadorService`.

## Um sinal, em uma frase

Um indicador é um número calculado (RSI(14) = 24). Uma **regra** (`RegraSinal`) é a interpretação desse número ("RSI < 30 = sobrevenda"). Um **sinal** (`Sinal`) é uma ocorrência dessa regra pra um ativo específico, com início (`data_ativacao`) e fim (`data_desativacao`, nulo enquanto vigente).

## Decisões já validadas com o usuário

1. **Persistência de regras**: hardcoded no código (lista `RegraSinal` com IDs fixos), sem tabela nova nem CRUD. A entidade já existe e migra fácil pra tabela depois, se precisar.
2. **Linguagem de condições v1**: só indicador vs. número fixo (ex: `RSI(14) < 30`). Cruzamentos entre indicadores (MACD vs linha de sinal, SMA20 vs SMA50) ficam pra uma iteração futura.
3. **Fonte do backtest**: recalcula os indicadores historicamente a partir de `cotacoes`, usando os métodos de cálculo puros do `IndicadorService` numa janela deslizante — nunca lê `indicadores_tecnicos` (que só tem o valor mais recente).

## Componentes

### Regras padrão (`src/app/domain/regras_sinal_padrao.py`)

Lista fixa de `RegraSinal`, com UUIDs literais (constantes, nunca gerados dinamicamente — um `Sinal` persistido referencia `regra_id`, que precisa continuar válido entre reinícios da aplicação):

```python
REGRAS_PADRAO: list[RegraSinal] = [
    RegraSinal(
        id=UUID("a1a1a1a1-0000-0000-0000-000000000001"),
        nome="Sobrevenda RSI",
        descricao="RSI(14) abaixo de 30 — condição técnica de sobrevenda.",
        condicoes={
            "tipo_indicador": "RSI",
            "parametros": {"periodo": 14},
            "operador": "menor_que",
            "valor_limiar": 30,
        },
        peso=Decimal("1.0"),
    ),
    RegraSinal(
        id=UUID("a1a1a1a1-0000-0000-0000-000000000002"),
        nome="Sobrecompra RSI",
        descricao="RSI(14) acima de 70 — condição técnica de sobrecompra.",
        condicoes={
            "tipo_indicador": "RSI",
            "parametros": {"periodo": 14},
            "operador": "maior_que",
            "valor_limiar": 70,
        },
        peso=Decimal("1.0"),
    ),
    RegraSinal(
        id=UUID("a1a1a1a1-0000-0000-0000-000000000003"),
        nome="Pico de Volume",
        descricao="Volume relativo(20) acima de 1.5x a média — atividade de negociação incomum.",
        condicoes={
            "tipo_indicador": "VOLUME_RELATIVO",
            "parametros": {"periodo": 20},
            "operador": "maior_que",
            "valor_limiar": 1.5,
        },
        peso=Decimal("0.5"),
    ),
]
```

Schema de `condicoes` (dict, chaves fixas pra v1):

| Chave | Tipo | Descrição |
|---|---|---|
| `tipo_indicador` | str | valor de `TipoIndicador` (ex: `"RSI"`) |
| `parametros` | dict | mesmo formato usado por `IndicadorTecnico.parametros` (ex: `{"periodo": 14}`) — usado pra localizar o indicador certo entre os vários calculados |
| `operador` | str | `"menor_que"` \| `"maior_que"` \| `"menor_igual"` \| `"maior_igual"` |
| `valor_limiar` | int/float | limiar de comparação |

### `avaliar_condicao(condicoes: dict, valor: Decimal) -> bool`

Função pura em `indicador_condicao.py` (ou dentro do próprio `sinal_service.py`, como função de módulo): aplica `operador` comparando `valor` com `Decimal(str(condicoes["valor_limiar"]))`. `ValueError` se `operador` for desconhecido (não deveria acontecer com as regras padrão, mas é uma checagem de sanidade barata).

### `SinalModel` + migration (tabela `sinais`)

| Coluna | Tipo |
|---|---|
| `id` | UUID, PK |
| `ativo_id` | UUID, FK → `ativos.id` |
| `regra_id` | UUID (sem FK — regras não são persistidas nesta etapa) |
| `data_ativacao` | DateTime(timezone=True) |
| `contexto` | JSON |
| `data_desativacao` | DateTime(timezone=True), nullable |

Sem constraint de unicidade — cada ativação é uma linha nova; o que garante "só um sinal vigente por ativo+regra" é a lógica do service, não o banco (ver abaixo).

### `SinalRepository` (interface + SQLAlchemy)

```python
class SinalRepository(ABC):
    def salvar(self, sinal: Sinal) -> None: ...
    def buscar_ativo(self, ativo_id: UUID, regra_id: UUID) -> Sinal | None: ...
```

`salvar` faz insert (sinal novo) ou update (sinal existente sendo desativado) por `id` — sem upsert por chave derivada, já que `Sinal` tem identidade própria (`id` gerado na criação, nunca recriado). `buscar_ativo` retorna o sinal com `data_desativacao IS NULL` pra aquele `(ativo_id, regra_id)`, se existir.

### `ResultadoBacktest` (novo value object, `src/app/domain/value_objects/resultado_backtest.py`)

```python
@dataclass
class ResultadoBacktest:
    regra_id: UUID
    ativo_id: UUID
    total_ocorrencias: int
    retorno_medio_5_pregoes: Decimal | None
    retorno_medio_20_pregoes: Decimal | None
    retorno_medio_60_pregoes: Decimal | None
```

`None` numa janela quando nenhuma ocorrência tem dados futuros suficientes pra medir aquele retorno (ex: ocorrência muito recente, sem 60 pregões seguintes ainda).

### `SinalService` (`src/app/services/sinal_service.py`)

Dependências: `AtivoRepository`, `CotacaoRepository`, `IndicadorService`, `SinalRepository`.

**`avaliar_ativo(self, ativo_id: UUID) -> list[Sinal]`**

```python
def avaliar_ativo(self, ativo_id: UUID) -> list[Sinal]:
    ativo = self._buscar_ativo(ativo_id)
    indicadores = self._indicador_service.calcular_todos(ativo.id)
    vigentes = []
    for regra in REGRAS_PADRAO:
        if not regra.ativa:
            continue
        indicador = self._encontrar_indicador(indicadores, regra.condicoes)
        satisfeita = indicador is not None and avaliar_condicao(regra.condicoes, indicador.valor)
        sinal_existente = self._sinal_repository.buscar_ativo(ativo.id, regra.id)
        if satisfeita and sinal_existente is None:
            novo = Sinal(id=uuid4(), ativo_id=ativo.id, regra_id=regra.id,
                         data_ativacao=datetime.now(UTC), contexto={"valor": str(indicador.valor)})
            self._sinal_repository.salvar(novo)
            vigentes.append(novo)
        elif not satisfeita and sinal_existente is not None:
            sinal_existente.data_desativacao = datetime.now(UTC)
            self._sinal_repository.salvar(sinal_existente)
        elif satisfeita and sinal_existente is not None:
            vigentes.append(sinal_existente)
    return vigentes
```

`_encontrar_indicador` localiza, na lista retornada por `calcular_todos`, o `IndicadorTecnico` cujo `tipo` e `parametros` batem com `condicoes["tipo_indicador"]`/`condicoes["parametros"]`. Se o indicador não foi calculado (histórico insuficiente), a condição é tratada como não satisfeita — mesma filosofia de "histórico insuficiente nunca quebra o fluxo" do `IndicadorService`.

**`backtest(self, regra_id: UUID, ativo_id: UUID) -> ResultadoBacktest`**

1. Resolve `ativo` e a `RegraSinal` (busca em `REGRAS_PADRAO` por `id`; `RegraNaoEncontradaError` se não existir — novo erro em `services/exceptions.py`).
2. Busca **toda** a série de `cotacoes` via `cotacao_repository.listar_por_ativo(ativo.id)` (já ordenado por `data_hora`) — sem filtrar ainda. Calcula `corte = datetime.now(UTC) - timedelta(days=730)` (24 meses ≈ 730 dias).
3. Pra cada índice `i` na lista completa de cotações onde `cotacoes[i].data_hora >= corte` (ou seja, o **dia da ocorrência** cai nos últimos 24 meses — mas o cálculo do indicador nesse dia usa `cotacoes[:i+1]`, a série completa até ali, não truncada em 24 meses — assim um indicador de janela longa como SMA(200) funciona corretamente mesmo pra ocorrências logo no início da janela de 24 meses), calcula o valor do indicador naquele dia com o método de cálculo puro correspondente ao `tipo_indicador` da regra, e avalia a condição.
4. Marca como "ocorrência" toda transição falso→verdadeiro (dia `i` satisfaz, dia `i-1` não satisfazia ou não existe).

Despacho `tipo_indicador` → método de cálculo: um dict fixo `{TipoIndicador.SMA: self._indicador_service.calcular_sma, TipoIndicador.RSI: self._indicador_service.calcular_rsi, TipoIndicador.MACD: self._indicador_service.calcular_macd, TipoIndicador.BOLLINGER: self._indicador_service.calcular_bollinger, TipoIndicador.VOLUME_RELATIVO: self._indicador_service.calcular_volume_relativo}`, chamado como `metodo(cotacoes[:i+1], **regra.condicoes["parametros"])` — funciona genericamente pros 5 tipos porque as chaves de `parametros` (ver tabela do item 1) já batem com os nomes dos parâmetros de cada método (`periodo`, ou `rapida`/`lenta`/`sinal`, ou `periodo`/`desvios`), mesmo que as regras v1 só usem RSI e Volume Relativo.
5. Pra cada ocorrência no dia `i`, calcula o retorno percentual do fechamento em `i+5`, `i+20`, `i+60` (quando esses dias existem na série), usando `(fechamento[i+N] / fechamento[i] - 1) * 100`.
6. `retorno_medio_N_pregoes` = média dos retornos coletados nessa janela entre todas as ocorrências (`None` se nenhuma ocorrência teve dados suficientes pra essa janela).

**`score_composto(self, ativo_id: UUID) -> Decimal`**

Soma `regra.peso` de cada `RegraSinal` com sinal vigente (`sinal_repository.buscar_ativo(ativo.id, regra.id) is not None`) pro ativo — não recalcula nada, só consulta o estado já persistido.

### Endpoints (`ativos.py`)

- `GET /ativos/{ativo_id}/sinais` → `avaliar_ativo`, retorna lista com nome/descrição da regra (`SinalResponse`, novo schema).
- `GET /ativos/{ativo_id}/sinais/{regra_id}/backtest` → `backtest`, retorna `ResultadoBacktestResponse`. 404 se `regra_id` não existe em `REGRAS_PADRAO` (`RegraNaoEncontradaError`) ou se `ativo_id` não existe.

Wiring em `deps.py`: `get_sinal_repository`, `get_sinal_service` (compõe `AtivoRepository` + `CotacaoRepository` + `IndicadorService` + `SinalRepository`).

## Erros

Novo `RegraNaoEncontradaError` em `services/exceptions.py` (backtest com `regra_id` desconhecido). Reutiliza `AtivoNaoEncontradoError` já existente.

## Testes

- Unitário de `avaliar_condicao`: cada operador, valor no limiar exato (`<=`/`>=` vs `<`/`>`).
- Unitário de `avaliar_ativo`: transição falso→verdadeiro cria `Sinal`; verdadeiro→falso desativa; verdadeiro→verdadeiro mantém sem duplicar; indicador ausente (histórico insuficiente) não quebra.
- Unitário de `backtest`: série sintética de cotações com uma queda e recuperação conhecida, verificando que a ocorrência e o retorno médio batem com o cálculo manual; caso sem ocorrências (`total_ocorrencias == 0`, todas as janelas `None`).
- Unitário de `score_composto`: soma correta dos pesos das regras vigentes.
- Integração de `SinalRepository`: salvar/buscar_ativo, ciclo ativação→desativação.
- Teste dos dois endpoints (200/404).

## Fora de escopo (explicitamente)

- Disparo automático via Scheduler.
- CRUD de regras via API.
- Condições indicador-vs-indicador (cruzamentos).
- Notificação de sinais (RF-09, `NotificacaoService`).
- Qualquer mudança em `indicadores_tecnicos` ou `cotacoes`.
