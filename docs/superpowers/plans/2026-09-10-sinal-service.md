# SinalService Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar detecção de sinais técnicos (regras avaliadas sobre indicadores, ativação/desativação persistida) e backtest histórico de 24 meses, expondo endpoints de consulta sob demanda.

**Architecture:** Mesmo padrão em camadas do `IndicadorService`: entidades de domínio (já existem) → model SQLAlchemy + migration → repository (interface + impl) → service (avaliação de regras + orquestração + backtest) → controller/endpoint, via injeção de dependência em `api/deps.py`. As regras (`RegraSinal`) ficam hardcoded numa lista Python com IDs fixos — sem tabela nova nem CRUD. O backtest nunca lê `indicadores_tecnicos` (que só guarda o valor mais recente) — ele recalcula os indicadores historicamente a partir de `cotacoes`, reusando os métodos de cálculo puros já existentes em `IndicadorService`.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, pandas + pandas-ta (via `IndicadorService`, não usado diretamente aqui), pytest.

**Spec:** `docs/superpowers/specs/2026-09-10-sinal-service-design.md`

## Global Constraints

- Regras ficam hardcoded em `REGRAS_PADRAO` (lista Python, `src/app/domain/regras_sinal_padrao.py`), com UUIDs **literais e fixos** — nunca gerados com `uuid4()` (senão `Sinal.regra_id` persistido no banco ficaria órfão a cada restart da aplicação).
- Condições v1 suportam só indicador vs. número fixo (`{"tipo_indicador": ..., "parametros": {...}, "operador": ..., "valor_limiar": ...}`). Nenhuma comparação indicador-vs-indicador.
- `avaliar_ativo` chama `IndicadorService.calcular_todos(ativo_id)` primeiro, pra garantir indicadores frescos antes de avaliar as regras.
- `backtest` nunca lê `indicadores_tecnicos` — reconstrói o valor do indicador em cada dia usando os métodos de cálculo puros do `IndicadorService` (`calcular_sma`, `calcular_rsi`, etc.) sobre `cotacoes[:i+1]` (série completa até aquele dia, não truncada em 24 meses — só os DIAS candidatos a ocorrência são filtrados aos últimos 24 meses, não o histórico usado pra calcular).
- "Ocorrência" no backtest = transição falso→verdadeiro da condição (dia `i` satisfaz, dia `i-1` não satisfazia ou não existe) — nunca conta todo dia em que a condição permanece verdadeira.
- `SinalRepository.salvar` faz insert-ou-update por `id` (sem upsert por chave derivada — `Sinal` tem identidade própria). Sem constraint de unicidade na tabela `sinais`.
- Histórico insuficiente pra calcular um indicador nunca lança exceção — a condição é tratada como não satisfeita.

---

## Task 1: Regras padrão, `ResultadoBacktest` e `RegraNaoEncontradaError`

**Files:**
- Create: `src/app/domain/regras_sinal_padrao.py`
- Create: `src/app/domain/value_objects/resultado_backtest.py`
- Modify: `src/app/services/exceptions.py`
- Test: `tests/unit/domain/test_regras_sinal_padrao.py`

**Interfaces:**
- Consumes: `RegraSinal` (`app.domain.entities.regra_sinal`, já existe)
- Produces: `REGRAS_PADRAO: list[RegraSinal]`, `buscar_regra_por_id(regra_id: UUID) -> RegraSinal | None`, `ResultadoBacktest` dataclass, `RegraNaoEncontradaError` — usados pelas Tasks 4, 5 e 6.

- [ ] **Step 1: Escrever o teste das regras padrão (RED)**

Arquivo `tests/unit/domain/test_regras_sinal_padrao.py`:

```python
from uuid import uuid4

from app.domain.regras_sinal_padrao import REGRAS_PADRAO, buscar_regra_por_id


def test_regras_padrao_tem_ids_unicos():
    ids = [regra.id for regra in REGRAS_PADRAO]
    assert len(ids) == len(set(ids))


def test_regras_padrao_todas_ativas_por_padrao():
    assert all(regra.ativa for regra in REGRAS_PADRAO)


def test_buscar_regra_por_id_encontra_regra_existente():
    primeira = REGRAS_PADRAO[0]

    encontrada = buscar_regra_por_id(primeira.id)

    assert encontrada is primeira


def test_buscar_regra_por_id_inexistente_retorna_none():
    assert buscar_regra_por_id(uuid4()) is None


def test_sobrevenda_rsi_condicoes():
    regra = next(r for r in REGRAS_PADRAO if r.nome == "Sobrevenda RSI")

    assert regra.condicoes == {
        "tipo_indicador": "RSI",
        "parametros": {"periodo": 14},
        "operador": "menor_que",
        "valor_limiar": 30,
    }


def test_pico_de_volume_condicoes():
    regra = next(r for r in REGRAS_PADRAO if r.nome == "Pico de Volume")

    assert regra.condicoes == {
        "tipo_indicador": "VOLUME_RELATIVO",
        "parametros": {"periodo": 20},
        "operador": "maior_que",
        "valor_limiar": 1.5,
    }
```

- [ ] **Step 2: Rodar e confirmar RED**

```bash
.venv/bin/python -m pytest tests/unit/domain/test_regras_sinal_padrao.py -q
```

Esperado: `ModuleNotFoundError: No module named 'app.domain.regras_sinal_padrao'`.

- [ ] **Step 3: Criar `regras_sinal_padrao.py`**

```python
from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from app.domain.entities.regra_sinal import RegraSinal

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
        descricao=(
            "Volume relativo(20) acima de 1.5x a média — atividade de negociação incomum."
        ),
        condicoes={
            "tipo_indicador": "VOLUME_RELATIVO",
            "parametros": {"periodo": 20},
            "operador": "maior_que",
            "valor_limiar": 1.5,
        },
        peso=Decimal("0.5"),
    ),
]


def buscar_regra_por_id(regra_id: UUID) -> RegraSinal | None:
    for regra in REGRAS_PADRAO:
        if regra.id == regra_id:
            return regra
    return None
```

- [ ] **Step 4: Rodar e confirmar GREEN**

```bash
.venv/bin/python -m pytest tests/unit/domain/test_regras_sinal_padrao.py -q
```

Esperado: `6 passed`.

- [ ] **Step 5: Criar `ResultadoBacktest`**

Arquivo `src/app/domain/value_objects/resultado_backtest.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID


@dataclass
class ResultadoBacktest:
    regra_id: UUID
    ativo_id: UUID
    total_ocorrencias: int
    retorno_medio_5_pregoes: Decimal | None
    retorno_medio_20_pregoes: Decimal | None
    retorno_medio_60_pregoes: Decimal | None
```

Nenhum teste dedicado — é uma dataclass sem lógica, validada indiretamente pelos testes de `backtest` na Task 5.

- [ ] **Step 6: Adicionar `RegraNaoEncontradaError`**

Em `src/app/services/exceptions.py`, adicionar ao final:

```python


class RegraNaoEncontradaError(Exception):
    pass
```

- [ ] **Step 7: Rodar `ruff check` e a suíte completa**

```bash
.venv/bin/ruff check src/ tests/
.venv/bin/python -m pytest -q
```

Esperado: lint limpo, todos os testes passando (171 anteriores + 6 novos = 177).

- [ ] **Step 8: Commit**

```bash
git add src/app/domain/regras_sinal_padrao.py src/app/domain/value_objects/resultado_backtest.py src/app/services/exceptions.py tests/unit/domain/test_regras_sinal_padrao.py
git commit -m "feat(sinais): adiciona regras de sinal padrao e ResultadoBacktest"
```

---

## Task 2: `SinalRepository` (interface + SQLAlchemy) com migration e teste de integração

**Files:**
- Create: `src/app/db/models/sinal.py`
- Create: `alembic/versions/c4d8e6f1a293_cria_tabela_sinais.py`
- Modify: `alembic/env.py`
- Modify: `tests/integration/conftest.py`
- Create: `src/app/repositories/interfaces/sinal_repository.py`
- Create: `src/app/repositories/sqlalchemy/sinal_repository.py`
- Test: `tests/integration/repositories/test_sinal_repository.py`

**Interfaces:**
- Consumes: `Sinal` (`app.domain.entities.sinal`, já existe)
- Produces: `SinalRepository.salvar(sinal) -> None`, `.buscar_ativo(ativo_id, regra_id) -> Sinal | None`, `.listar_por_ativo(ativo_id) -> list[Sinal]` — usados pelo `SinalService` (Tasks 4/5) e pelo fake (Task 3).

- [ ] **Step 1: Criar o model**

Arquivo `src/app/db/models/sinal.py`:

```python
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SinalModel(Base):
    __tablename__ = "sinais"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    ativo_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("ativos.id"), nullable=False)
    regra_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    data_ativacao: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    contexto: Mapped[dict] = mapped_column(JSON, nullable=False)
    data_desativacao: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
```

- [ ] **Step 2: Registrar o model em `alembic/env.py` e `tests/integration/conftest.py`**

Em `alembic/env.py`, junto aos outros imports de model (ordem alfabética):

```python
from app.db.models.sinal import SinalModel
```

Em `tests/integration/conftest.py`, mesmo import, mesma posição alfabética.

- [ ] **Step 3: Criar a migration**

Verificar o head atual:

```bash
DATABASE_URL="postgresql://insightflow:insightflow@localhost:5432/insightflow" .venv/bin/alembic heads
```

Deve mostrar `b8c1d3e9f2a7`. Criar `alembic/versions/c4d8e6f1a293_cria_tabela_sinais.py`:

```python
"""cria tabela sinais

Revision ID: c4d8e6f1a293
Revises: b8c1d3e9f2a7
Create Date: 2026-09-10 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c4d8e6f1a293"
down_revision: str | Sequence[str] | None = "b8c1d3e9f2a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sinais",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ativo_id", sa.Uuid(), nullable=False),
        sa.Column("regra_id", sa.Uuid(), nullable=False),
        sa.Column("data_ativacao", sa.DateTime(timezone=True), nullable=False),
        sa.Column("contexto", sa.JSON(), nullable=False),
        sa.Column("data_desativacao", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["ativo_id"],
            ["ativos.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("sinais")
```

- [ ] **Step 4: Aplicar e verificar o ciclo upgrade/downgrade/upgrade**

```bash
docker compose up -d postgres
DATABASE_URL="postgresql://insightflow:insightflow@localhost:5432/insightflow" .venv/bin/alembic upgrade head
DATABASE_URL="postgresql://insightflow:insightflow@localhost:5432/insightflow" .venv/bin/alembic downgrade -1
DATABASE_URL="postgresql://insightflow:insightflow@localhost:5432/insightflow" .venv/bin/alembic upgrade head
```

Esperado: os três comandos rodam sem erro.

- [ ] **Step 5: Escrever o teste de integração do repository (RED)**

Arquivo `tests/integration/repositories/test_sinal_repository.py`:

```python
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.domain.entities.ativo import Ativo
from app.domain.entities.sinal import Sinal
from app.domain.enums.tipo_ativo import TipoAtivo
from app.repositories.sqlalchemy.ativo_repository import SqlAlchemyAtivoRepository
from app.repositories.sqlalchemy.sinal_repository import SqlAlchemySinalRepository

pytestmark = pytest.mark.integration


def _novo_ativo(session) -> Ativo:
    ativo = Ativo(
        id=uuid4(),
        ticker="PETR4",
        nome="Petrobras PN",
        tipo=TipoAtivo.ACAO,
        setor="Petróleo e Gás",
        moeda="BRL",
        fonte_dados="manual",
    )
    SqlAlchemyAtivoRepository(session).salvar(ativo)
    return ativo


def _sinal(ativo_id, regra_id=None, data_desativacao=None) -> Sinal:
    return Sinal(
        id=uuid4(),
        ativo_id=ativo_id,
        regra_id=regra_id or uuid4(),
        data_ativacao=datetime(2024, 1, 1, tzinfo=UTC),
        contexto={"valor": "25.5"},
        data_desativacao=data_desativacao,
    )


def test_salvar_e_buscar_ativo_retorna_o_sinal_vigente(session):
    ativo = _novo_ativo(session)
    repo = SqlAlchemySinalRepository(session)
    regra_id = uuid4()
    sinal = _sinal(ativo.id, regra_id=regra_id)

    repo.salvar(sinal)

    encontrado = repo.buscar_ativo(ativo.id, regra_id)
    assert encontrado is not None
    assert encontrado.id == sinal.id
    assert encontrado.data_desativacao is None


def test_buscar_ativo_sem_sinal_vigente_retorna_none(session):
    ativo = _novo_ativo(session)
    repo = SqlAlchemySinalRepository(session)

    assert repo.buscar_ativo(ativo.id, uuid4()) is None


def test_buscar_ativo_ignora_sinal_ja_desativado(session):
    ativo = _novo_ativo(session)
    repo = SqlAlchemySinalRepository(session)
    regra_id = uuid4()
    repo.salvar(_sinal(ativo.id, regra_id=regra_id, data_desativacao=datetime(2024, 2, 1, tzinfo=UTC)))

    assert repo.buscar_ativo(ativo.id, regra_id) is None


def test_salvar_atualiza_sinal_existente_em_vez_de_duplicar(session):
    ativo = _novo_ativo(session)
    repo = SqlAlchemySinalRepository(session)
    regra_id = uuid4()
    sinal = _sinal(ativo.id, regra_id=regra_id)
    repo.salvar(sinal)

    sinal.data_desativacao = datetime(2024, 3, 1, tzinfo=UTC)
    repo.salvar(sinal)

    assert repo.buscar_ativo(ativo.id, regra_id) is None
    todos = repo.listar_por_ativo(ativo.id)
    assert len(todos) == 1
    assert todos[0].data_desativacao == datetime(2024, 3, 1, tzinfo=UTC)


def test_listar_por_ativo_retorna_ativos_e_desativados(session):
    ativo = _novo_ativo(session)
    repo = SqlAlchemySinalRepository(session)
    repo.salvar(_sinal(ativo.id))
    repo.salvar(_sinal(ativo.id, data_desativacao=datetime(2024, 2, 1, tzinfo=UTC)))

    assert len(repo.listar_por_ativo(ativo.id)) == 2


def test_listar_por_ativo_sem_sinais_retorna_lista_vazia(session):
    ativo = _novo_ativo(session)
    repo = SqlAlchemySinalRepository(session)

    assert repo.listar_por_ativo(ativo.id) == []
```

- [ ] **Step 6: Rodar e confirmar RED**

```bash
.venv/bin/python -m pytest tests/integration/repositories/test_sinal_repository.py -q
```

Esperado: `ModuleNotFoundError: No module named 'app.repositories.interfaces.sinal_repository'`.

- [ ] **Step 7: Criar a interface**

Arquivo `src/app/repositories/interfaces/sinal_repository.py`:

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.sinal import Sinal


class SinalRepository(ABC):
    @abstractmethod
    def salvar(self, sinal: Sinal) -> None: ...

    @abstractmethod
    def buscar_ativo(self, ativo_id: UUID, regra_id: UUID) -> Sinal | None: ...

    @abstractmethod
    def listar_por_ativo(self, ativo_id: UUID) -> list[Sinal]: ...
```

- [ ] **Step 8: Criar a implementação SQLAlchemy**

Arquivo `src/app/repositories/sqlalchemy/sinal_repository.py`:

```python
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.sinal import SinalModel
from app.domain.entities.sinal import Sinal
from app.repositories.interfaces.sinal_repository import SinalRepository


class SqlAlchemySinalRepository(SinalRepository):
    def __init__(self, session: Session):
        self._session = session

    def salvar(self, sinal: Sinal) -> None:
        modelo = self._session.get(SinalModel, sinal.id)
        if modelo is None:
            modelo = SinalModel(id=sinal.id)
            self._session.add(modelo)

        modelo.ativo_id = sinal.ativo_id
        modelo.regra_id = sinal.regra_id
        modelo.data_ativacao = sinal.data_ativacao
        modelo.contexto = sinal.contexto
        modelo.data_desativacao = sinal.data_desativacao
        self._session.commit()

    def buscar_ativo(self, ativo_id: UUID, regra_id: UUID) -> Sinal | None:
        modelo = self._session.scalar(
            select(SinalModel).where(
                SinalModel.ativo_id == ativo_id,
                SinalModel.regra_id == regra_id,
                SinalModel.data_desativacao.is_(None),
            )
        )
        return self._para_entidade(modelo) if modelo is not None else None

    def listar_por_ativo(self, ativo_id: UUID) -> list[Sinal]:
        modelos = self._session.scalars(
            select(SinalModel)
            .where(SinalModel.ativo_id == ativo_id)
            .order_by(SinalModel.data_ativacao)
        )
        return [self._para_entidade(modelo) for modelo in modelos]

    @staticmethod
    def _para_entidade(modelo: SinalModel) -> Sinal:
        return Sinal(
            id=modelo.id,
            ativo_id=modelo.ativo_id,
            regra_id=modelo.regra_id,
            data_ativacao=modelo.data_ativacao,
            contexto=modelo.contexto,
            data_desativacao=modelo.data_desativacao,
        )
```

- [ ] **Step 9: Rodar e confirmar GREEN**

```bash
.venv/bin/python -m pytest tests/integration/repositories/test_sinal_repository.py -q
```

Esperado: `6 passed`.

- [ ] **Step 10: Rodar `ruff check` e a suíte completa**

```bash
.venv/bin/ruff check src/ tests/
.venv/bin/python -m pytest -q
```

Esperado: lint limpo, todos os testes passando.

- [ ] **Step 11: Commit**

```bash
git add src/app/db/models/sinal.py alembic/versions/c4d8e6f1a293_cria_tabela_sinais.py alembic/env.py tests/integration/conftest.py src/app/repositories/interfaces/sinal_repository.py src/app/repositories/sqlalchemy/sinal_repository.py tests/integration/repositories/test_sinal_repository.py
git commit -m "feat(sinais): cria tabela sinais e SinalRepository"
```

---

## Task 3: `FakeSinalRepository`

**Files:**
- Create: `tests/fixtures/fake_sinal_repository.py`

**Interfaces:**
- Consumes: `SinalRepository` (Task 2)
- Produces: `FakeSinalRepository` — usado pelos testes unitários do `SinalService` (Tasks 4/5) e do controller (Task 6).

Sem ciclo RED/GREEN — fixture de teste sem lógica de negócio, mesmo espírito de `FakeCotacaoRepository`/`FakeIndicadorTecnicoRepository`.

- [ ] **Step 1: Criar o fake**

Arquivo `tests/fixtures/fake_sinal_repository.py`:

```python
from __future__ import annotations

from uuid import UUID

from app.domain.entities.sinal import Sinal
from app.repositories.interfaces.sinal_repository import SinalRepository


class FakeSinalRepository(SinalRepository):
    def __init__(self) -> None:
        self._sinais: dict[UUID, Sinal] = {}

    def salvar(self, sinal: Sinal) -> None:
        self._sinais[sinal.id] = sinal

    def buscar_ativo(self, ativo_id: UUID, regra_id: UUID) -> Sinal | None:
        for sinal in self._sinais.values():
            if (
                sinal.ativo_id == ativo_id
                and sinal.regra_id == regra_id
                and sinal.data_desativacao is None
            ):
                return sinal
        return None

    def listar_por_ativo(self, ativo_id: UUID) -> list[Sinal]:
        return [sinal for sinal in self._sinais.values() if sinal.ativo_id == ativo_id]
```

- [ ] **Step 2: Rodar `ruff check`**

```bash
.venv/bin/ruff check tests/fixtures/fake_sinal_repository.py
```

Esperado: `All checks passed!`

- [ ] **Step 3: Commit**

```bash
git add tests/fixtures/fake_sinal_repository.py
git commit -m "test(sinais): adiciona FakeSinalRepository"
```

---

## Task 4: `avaliar_condicao`, `SinalService.avaliar_ativo` e `score_composto`

**Files:**
- Create: `src/app/services/sinal_service.py`
- Test: `tests/unit/services/test_sinal_service.py`

**Interfaces:**
- Consumes: `IndicadorService` (`app.services.indicador_service`, já existe — instanciado diretamente nos testes com fakes, igual `AtivoService` faz com `DadosMercadoService`), `IndicadorTecnico`, `TipoIndicador`, `REGRAS_PADRAO`/`buscar_regra_por_id` (Task 1), `SinalRepository` (Task 2), `AtivoNaoEncontradoError`
- Produces: `SinalService.__init__(ativo_repository, cotacao_repository, indicador_service, sinal_repository)`, `.avaliar_ativo(ativo_id: UUID) -> list[Sinal]`, `.score_composto(ativo_id: UUID) -> Decimal` — `avaliar_ativo` usado pela Task 6 (endpoint); `.backtest` (Task 5) é adicionado na mesma classe depois.

- [ ] **Step 1: Escrever os testes de `avaliar_condicao` (RED)**

Arquivo `tests/unit/services/test_sinal_service.py`:

```python
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.entities.ativo import Ativo
from app.domain.entities.cotacao import Cotacao
from app.domain.entities.sinal import Sinal
from app.domain.enums.tipo_ativo import TipoAtivo
from app.services.exceptions import AtivoNaoEncontradoError
from app.services.indicador_service import IndicadorService
from app.services.sinal_service import SinalService, avaliar_condicao
from tests.fixtures.fake_ativo_repository import FakeAtivoRepository
from tests.fixtures.fake_cotacao_repository import FakeCotacaoRepository
from tests.fixtures.fake_indicador_tecnico_repository import FakeIndicadorTecnicoRepository
from tests.fixtures.fake_sinal_repository import FakeSinalRepository

_ATIVO = Ativo(
    id=uuid4(),
    ticker="PETR4",
    nome="Petrobras PN",
    tipo=TipoAtivo.ACAO,
    setor="Petroleo e Gas",
    moeda="BRL",
    fonte_dados="manual",
)


def test_avaliar_condicao_menor_que():
    condicoes = {"operador": "menor_que", "valor_limiar": 30}
    assert avaliar_condicao(condicoes, Decimal("29")) is True
    assert avaliar_condicao(condicoes, Decimal("30")) is False
    assert avaliar_condicao(condicoes, Decimal("31")) is False


def test_avaliar_condicao_maior_que():
    condicoes = {"operador": "maior_que", "valor_limiar": 70}
    assert avaliar_condicao(condicoes, Decimal("71")) is True
    assert avaliar_condicao(condicoes, Decimal("70")) is False


def test_avaliar_condicao_menor_igual():
    condicoes = {"operador": "menor_igual", "valor_limiar": 30}
    assert avaliar_condicao(condicoes, Decimal("30")) is True
    assert avaliar_condicao(condicoes, Decimal("31")) is False


def test_avaliar_condicao_maior_igual():
    condicoes = {"operador": "maior_igual", "valor_limiar": 70}
    assert avaliar_condicao(condicoes, Decimal("70")) is True
    assert avaliar_condicao(condicoes, Decimal("69")) is False
```

- [ ] **Step 2: Rodar e confirmar RED**

```bash
.venv/bin/python -m pytest tests/unit/services/test_sinal_service.py -q
```

Esperado: `ModuleNotFoundError: No module named 'app.services.sinal_service'`.

- [ ] **Step 3: Criar `sinal_service.py` com `avaliar_condicao`**

Arquivo `src/app/services/sinal_service.py`:

```python
from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from app.domain.entities.ativo import Ativo
from app.domain.entities.indicador_tecnico import IndicadorTecnico
from app.domain.entities.sinal import Sinal
from app.domain.enums.tipo_indicador import TipoIndicador
from app.domain.regras_sinal_padrao import REGRAS_PADRAO
from app.repositories.interfaces.ativo_repository import AtivoRepository
from app.repositories.interfaces.cotacao_repository import CotacaoRepository
from app.repositories.interfaces.sinal_repository import SinalRepository
from app.services.exceptions import AtivoNaoEncontradoError
from app.services.indicador_service import IndicadorService

_OPERADORES: dict[str, Callable[[Decimal, Decimal], bool]] = {
    "menor_que": lambda valor, limiar: valor < limiar,
    "maior_que": lambda valor, limiar: valor > limiar,
    "menor_igual": lambda valor, limiar: valor <= limiar,
    "maior_igual": lambda valor, limiar: valor >= limiar,
}


def avaliar_condicao(condicoes: dict, valor: Decimal) -> bool:
    operador = _OPERADORES[condicoes["operador"]]
    limiar = Decimal(str(condicoes["valor_limiar"]))
    return operador(valor, limiar)


def _encontrar_indicador(
    indicadores: list[IndicadorTecnico], condicoes: dict
) -> IndicadorTecnico | None:
    tipo = TipoIndicador(condicoes["tipo_indicador"])
    parametros = condicoes["parametros"]
    for indicador in indicadores:
        if indicador.tipo == tipo and indicador.parametros == parametros:
            return indicador
    return None


class SinalService:
    def __init__(
        self,
        ativo_repository: AtivoRepository,
        cotacao_repository: CotacaoRepository,
        indicador_service: IndicadorService,
        sinal_repository: SinalRepository,
    ):
        self._ativo_repository = ativo_repository
        self._cotacao_repository = cotacao_repository
        self._indicador_service = indicador_service
        self._sinal_repository = sinal_repository

    def _buscar_ativo(self, ativo_id: UUID) -> Ativo:
        ativo = self._ativo_repository.buscar_por_id(ativo_id)
        if ativo is None:
            raise AtivoNaoEncontradoError(ativo_id)
        return ativo
```

- [ ] **Step 4: Rodar e confirmar GREEN**

```bash
.venv/bin/python -m pytest tests/unit/services/test_sinal_service.py -q
```

Esperado: `4 passed`.

- [ ] **Step 5: Escrever os testes de `avaliar_ativo` (RED)**

Adicionar ao final de `tests/unit/services/test_sinal_service.py`:

```python
def _cotacoes_rsi_baixo(ativo_id) -> list[Cotacao]:
    precos = [20.0] * 30 + [20 - i * 1.0 for i in range(1, 11)]
    base = datetime.now(UTC) - timedelta(days=len(precos) - 1)
    return [
        Cotacao(
            id=uuid4(),
            ativo_id=ativo_id,
            data_hora=base + timedelta(days=i),
            abertura=Decimal(str(preco)),
            maxima=Decimal(str(preco)),
            minima=Decimal(str(preco)),
            fechamento=Decimal(str(preco)),
            volume=Decimal("1000000"),
        )
        for i, preco in enumerate(precos)
    ]


def _cotacoes_rsi_alto(ativo_id) -> list[Cotacao]:
    precos = [10 + i * 0.1 for i in range(40)]
    base = datetime.now(UTC) - timedelta(days=len(precos) - 1)
    return [
        Cotacao(
            id=uuid4(),
            ativo_id=ativo_id,
            data_hora=base + timedelta(days=i),
            abertura=Decimal(str(preco)),
            maxima=Decimal(str(preco)),
            minima=Decimal(str(preco)),
            fechamento=Decimal(str(preco)),
            volume=Decimal("1000000"),
        )
        for i, preco in enumerate(precos)
    ]


def _cotacoes_recuperacao(ativo_id, a_partir_de: datetime) -> list[Cotacao]:
    precos = [10 + i * 0.5 for i in range(1, 21)]
    return [
        Cotacao(
            id=uuid4(),
            ativo_id=ativo_id,
            data_hora=a_partir_de + timedelta(days=i),
            abertura=Decimal(str(preco)),
            maxima=Decimal(str(preco)),
            minima=Decimal(str(preco)),
            fechamento=Decimal(str(preco)),
            volume=Decimal("1000000"),
        )
        for i, preco in enumerate(precos, start=1)
    ]


def _service(ativo_repository=None, cotacao_repository=None, sinal_repository=None):
    ativo_repository = ativo_repository or FakeAtivoRepository()
    cotacao_repository = cotacao_repository or FakeCotacaoRepository()
    indicador_service = IndicadorService(
        ativo_repository, cotacao_repository, FakeIndicadorTecnicoRepository()
    )
    return SinalService(
        ativo_repository,
        cotacao_repository,
        indicador_service,
        sinal_repository or FakeSinalRepository(),
    )


_REGRA_SOBREVENDA_RSI = next(r for r in REGRAS_PADRAO if r.nome == "Sobrevenda RSI")


def test_avaliar_ativo_cria_sinal_quando_condicao_passa_a_satisfeita():
    ativo_repository = FakeAtivoRepository()
    ativo_repository.salvar(_ATIVO)
    cotacao_repository = FakeCotacaoRepository()
    cotacao_repository.salvar_muitas(_cotacoes_rsi_baixo(_ATIVO.id))
    sinal_repository = FakeSinalRepository()
    service = _service(ativo_repository, cotacao_repository, sinal_repository)

    vigentes = service.avaliar_ativo(_ATIVO.id)

    sinais_rsi = [s for s in vigentes if s.regra_id == _REGRA_SOBREVENDA_RSI.id]
    assert len(sinais_rsi) == 1
    assert sinais_rsi[0].data_desativacao is None
    assert sinal_repository.buscar_ativo(_ATIVO.id, _REGRA_SOBREVENDA_RSI.id) is not None


def test_avaliar_ativo_mantem_o_mesmo_sinal_sem_duplicar():
    ativo_repository = FakeAtivoRepository()
    ativo_repository.salvar(_ATIVO)
    cotacao_repository = FakeCotacaoRepository()
    cotacao_repository.salvar_muitas(_cotacoes_rsi_baixo(_ATIVO.id))
    sinal_repository = FakeSinalRepository()
    service = _service(ativo_repository, cotacao_repository, sinal_repository)
    primeira = service.avaliar_ativo(_ATIVO.id)
    id_primeiro_sinal = next(
        s.id for s in primeira if s.regra_id == _REGRA_SOBREVENDA_RSI.id
    )

    segunda = service.avaliar_ativo(_ATIVO.id)

    id_segundo_sinal = next(
        s.id for s in segunda if s.regra_id == _REGRA_SOBREVENDA_RSI.id
    )
    assert id_segundo_sinal == id_primeiro_sinal
    assert len(sinal_repository.listar_por_ativo(_ATIVO.id)) == 1


def test_avaliar_ativo_desativa_sinal_quando_condicao_deixa_de_ser_satisfeita():
    ativo_repository = FakeAtivoRepository()
    ativo_repository.salvar(_ATIVO)
    cotacao_repository = FakeCotacaoRepository()
    declinio = _cotacoes_rsi_baixo(_ATIVO.id)
    cotacao_repository.salvar_muitas(declinio)
    sinal_repository = FakeSinalRepository()
    service = _service(ativo_repository, cotacao_repository, sinal_repository)
    service.avaliar_ativo(_ATIVO.id)
    assert sinal_repository.buscar_ativo(_ATIVO.id, _REGRA_SOBREVENDA_RSI.id) is not None

    cotacao_repository.salvar_muitas(_cotacoes_recuperacao(_ATIVO.id, declinio[-1].data_hora))
    vigentes = service.avaliar_ativo(_ATIVO.id)

    assert all(s.regra_id != _REGRA_SOBREVENDA_RSI.id for s in vigentes)
    assert sinal_repository.buscar_ativo(_ATIVO.id, _REGRA_SOBREVENDA_RSI.id) is None
    historico = sinal_repository.listar_por_ativo(_ATIVO.id)
    sinal_desativado = next(s for s in historico if s.regra_id == _REGRA_SOBREVENDA_RSI.id)
    assert sinal_desativado.data_desativacao is not None


def test_avaliar_ativo_com_ativo_inexistente_lanca_erro():
    service = _service()

    with pytest.raises(AtivoNaoEncontradoError):
        service.avaliar_ativo(uuid4())
```

Nota sobre `test_avaliar_ativo_mantem_o_mesmo_sinal_sem_duplicar`: o assert final espera exatamente 1 sinal persistido, não 1 por regra ativa — `_cotacoes_rsi_baixo` só satisfaz a condição de "Sobrevenda RSI" (RSI baixo); "Sobrecompra RSI" (RSI>70) nunca é satisfeita por essa série, e "Pico de Volume" também não (volume constante = relativo 1.0, não > 1.5).

- [ ] **Step 6: Rodar e confirmar RED**

```bash
.venv/bin/python -m pytest tests/unit/services/test_sinal_service.py -q -k avaliar_ativo
```

Esperado: `AttributeError: 'SinalService' object has no attribute 'avaliar_ativo'`.

- [ ] **Step 7: Implementar `avaliar_ativo`**

Adicionar em `src/app/services/sinal_service.py`, dentro da classe `SinalService`, logo após `__init__`:

```python
    def avaliar_ativo(self, ativo_id: UUID) -> list[Sinal]:
        ativo = self._buscar_ativo(ativo_id)
        indicadores = self._indicador_service.calcular_todos(ativo.id)
        vigentes: list[Sinal] = []
        for regra in REGRAS_PADRAO:
            if not regra.ativa:
                continue
            indicador = _encontrar_indicador(indicadores, regra.condicoes)
            satisfeita = indicador is not None and avaliar_condicao(
                regra.condicoes, indicador.valor
            )
            sinal_existente = self._sinal_repository.buscar_ativo(ativo.id, regra.id)
            if satisfeita and sinal_existente is None:
                novo = Sinal(
                    id=uuid4(),
                    ativo_id=ativo.id,
                    regra_id=regra.id,
                    data_ativacao=datetime.now(UTC),
                    contexto={"valor": str(indicador.valor)},
                    data_desativacao=None,
                )
                self._sinal_repository.salvar(novo)
                vigentes.append(novo)
            elif not satisfeita and sinal_existente is not None:
                sinal_existente.data_desativacao = datetime.now(UTC)
                self._sinal_repository.salvar(sinal_existente)
            elif satisfeita and sinal_existente is not None:
                vigentes.append(sinal_existente)
        return vigentes
```

- [ ] **Step 8: Rodar e confirmar GREEN**

```bash
.venv/bin/python -m pytest tests/unit/services/test_sinal_service.py -q -k avaliar_ativo
```

Esperado: `4 passed`.

- [ ] **Step 9: Escrever os testes de `score_composto` (RED)**

Adicionar ao final de `tests/unit/services/test_sinal_service.py`:

```python
def test_score_composto_soma_pesos_das_regras_vigentes():
    ativo_repository = FakeAtivoRepository()
    ativo_repository.salvar(_ATIVO)
    sinal_repository = FakeSinalRepository()
    regra_volume = next(r for r in REGRAS_PADRAO if r.nome == "Pico de Volume")
    sinal_repository.salvar(
        Sinal(
            id=uuid4(),
            ativo_id=_ATIVO.id,
            regra_id=_REGRA_SOBREVENDA_RSI.id,
            data_ativacao=datetime.now(UTC),
            contexto={},
            data_desativacao=None,
        )
    )
    sinal_repository.salvar(
        Sinal(
            id=uuid4(),
            ativo_id=_ATIVO.id,
            regra_id=regra_volume.id,
            data_ativacao=datetime.now(UTC),
            contexto={},
            data_desativacao=None,
        )
    )
    service = _service(ativo_repository, sinal_repository=sinal_repository)

    score = service.score_composto(_ATIVO.id)

    assert score == _REGRA_SOBREVENDA_RSI.peso + regra_volume.peso


def test_score_composto_sem_sinais_vigentes_retorna_zero():
    ativo_repository = FakeAtivoRepository()
    ativo_repository.salvar(_ATIVO)
    service = _service(ativo_repository)

    assert service.score_composto(_ATIVO.id) == Decimal("0")
```

(`Sinal` já foi importado no Step 1 deste arquivo — nenhum import novo necessário aqui.)

- [ ] **Step 10: Rodar e confirmar RED**

```bash
.venv/bin/python -m pytest tests/unit/services/test_sinal_service.py -q -k score_composto
```

Esperado: `AttributeError: 'SinalService' object has no attribute 'score_composto'`.

- [ ] **Step 11: Implementar `score_composto`**

Adicionar em `src/app/services/sinal_service.py`, logo após `avaliar_ativo`:

```python
    def score_composto(self, ativo_id: UUID) -> Decimal:
        ativo = self._buscar_ativo(ativo_id)
        total = Decimal("0")
        for regra in REGRAS_PADRAO:
            if self._sinal_repository.buscar_ativo(ativo.id, regra.id) is not None:
                total += regra.peso
        return total
```

- [ ] **Step 12: Rodar todos os testes do arquivo e confirmar GREEN**

```bash
.venv/bin/python -m pytest tests/unit/services/test_sinal_service.py -q
```

Esperado: `12 passed`.

- [ ] **Step 13: Rodar `ruff check` e a suíte completa**

```bash
.venv/bin/ruff check src/ tests/
.venv/bin/python -m pytest -q
```

Esperado: lint limpo, todos os testes passando.

- [ ] **Step 14: Commit**

```bash
git add src/app/services/sinal_service.py tests/unit/services/test_sinal_service.py
git commit -m "feat(sinais): adiciona avaliar_condicao, SinalService.avaliar_ativo e score_composto"
```

---

## Task 5: `SinalService.backtest`

**Files:**
- Modify: `src/app/services/sinal_service.py`
- Modify: `tests/unit/services/test_sinal_service.py`

**Interfaces:**
- Consumes: `buscar_regra_por_id` (Task 1), `RegraNaoEncontradaError` (Task 1), `ResultadoBacktest` (Task 1), os 5 métodos de cálculo do `IndicadorService` (`calcular_sma`, `calcular_rsi`, `calcular_macd`, `calcular_bollinger`, `calcular_volume_relativo`, já existem)
- Produces: `SinalService.backtest(regra_id: UUID, ativo_id: UUID) -> ResultadoBacktest` — usado pela Task 6 (endpoint).

- [ ] **Step 1: Escrever os testes de `backtest` (RED)**

Em `tests/unit/services/test_sinal_service.py`, trocar a linha de import `from app.services.exceptions import AtivoNaoEncontradoError` por `from app.services.exceptions import AtivoNaoEncontradoError, RegraNaoEncontradaError`. Depois, adicionar ao final do arquivo:

```python
def _cotacoes_backtest_rsi(ativo_id) -> list[Cotacao]:
    precos = (
        [20.0] * 30
        + [20 - i * 1.0 for i in range(1, 11)]
        + [10 + i * 0.5 for i in range(1, 21)]
    )
    base = datetime.now(UTC) - timedelta(days=len(precos) - 1)
    return [
        Cotacao(
            id=uuid4(),
            ativo_id=ativo_id,
            data_hora=base + timedelta(days=i),
            abertura=Decimal(str(preco)),
            maxima=Decimal(str(preco)),
            minima=Decimal(str(preco)),
            fechamento=Decimal(str(preco)),
            volume=Decimal("1000000"),
        )
        for i, preco in enumerate(precos)
    ]


def test_backtest_encontra_ocorrencia_e_calcula_retornos_medios():
    ativo_repository = FakeAtivoRepository()
    ativo_repository.salvar(_ATIVO)
    cotacao_repository = FakeCotacaoRepository()
    cotacao_repository.salvar_muitas(_cotacoes_backtest_rsi(_ATIVO.id))
    service = _service(ativo_repository, cotacao_repository)

    resultado = service.backtest(_REGRA_SOBREVENDA_RSI.id, _ATIVO.id)

    assert resultado.regra_id == _REGRA_SOBREVENDA_RSI.id
    assert resultado.ativo_id == _ATIVO.id
    assert resultado.total_ocorrencias == 1
    assert round(resultado.retorno_medio_5_pregoes, 2) == Decimal("-26.32")
    assert round(resultado.retorno_medio_20_pregoes, 2) == Decimal("-18.42")
    assert resultado.retorno_medio_60_pregoes is None


def test_backtest_sem_ocorrencias_retorna_zero_e_janelas_nulas():
    ativo_repository = FakeAtivoRepository()
    ativo_repository.salvar(_ATIVO)
    cotacao_repository = FakeCotacaoRepository()
    cotacao_repository.salvar_muitas(_cotacoes_rsi_alto(_ATIVO.id))
    service = _service(ativo_repository, cotacao_repository)

    resultado = service.backtest(_REGRA_SOBREVENDA_RSI.id, _ATIVO.id)

    assert resultado.total_ocorrencias == 0
    assert resultado.retorno_medio_5_pregoes is None
    assert resultado.retorno_medio_20_pregoes is None
    assert resultado.retorno_medio_60_pregoes is None


def test_backtest_com_regra_inexistente_lanca_erro():
    ativo_repository = FakeAtivoRepository()
    ativo_repository.salvar(_ATIVO)
    service = _service(ativo_repository)

    with pytest.raises(RegraNaoEncontradaError):
        service.backtest(uuid4(), _ATIVO.id)


def test_backtest_com_ativo_inexistente_lanca_erro():
    service = _service()

    with pytest.raises(AtivoNaoEncontradoError):
        service.backtest(_REGRA_SOBREVENDA_RSI.id, uuid4())
```

- [ ] **Step 2: Rodar e confirmar RED**

```bash
.venv/bin/python -m pytest tests/unit/services/test_sinal_service.py -q -k backtest
```

Esperado: `AttributeError: 'SinalService' object has no attribute 'backtest'`.

- [ ] **Step 3: Implementar `backtest`**

No topo de `src/app/services/sinal_service.py`, duas mudanças em linhas de import já existentes e duas linhas novas:

1. Trocar `from datetime import UTC, datetime` por `from datetime import UTC, datetime, timedelta`.
2. Trocar `from app.services.exceptions import AtivoNaoEncontradoError` por `from app.services.exceptions import AtivoNaoEncontradoError, RegraNaoEncontradaError`.
3. Adicionar estas duas linhas novas (ordem alfabética, junto aos imports de `app.domain...`/`app.services...`):

```python
from app.domain.regras_sinal_padrao import buscar_regra_por_id
from app.domain.value_objects.resultado_backtest import ResultadoBacktest
```

Adicionar em `SinalService`, logo após `score_composto`:

```python
    def backtest(self, regra_id: UUID, ativo_id: UUID) -> ResultadoBacktest:
        ativo = self._buscar_ativo(ativo_id)
        regra = buscar_regra_por_id(regra_id)
        if regra is None:
            raise RegraNaoEncontradaError(regra_id)

        cotacoes = self._cotacao_repository.listar_por_ativo(ativo.id)
        corte = datetime.now(UTC) - timedelta(days=730)

        metodo_calculo = {
            TipoIndicador.SMA: self._indicador_service.calcular_sma,
            TipoIndicador.RSI: self._indicador_service.calcular_rsi,
            TipoIndicador.MACD: self._indicador_service.calcular_macd,
            TipoIndicador.BOLLINGER: self._indicador_service.calcular_bollinger,
            TipoIndicador.VOLUME_RELATIVO: self._indicador_service.calcular_volume_relativo,
        }[TipoIndicador(regra.condicoes["tipo_indicador"])]
        parametros = regra.condicoes["parametros"]

        ocorrencias: list[int] = []
        satisfeita_anterior = False
        for i, cotacao in enumerate(cotacoes):
            indicador = metodo_calculo(cotacoes[: i + 1], **parametros)
            satisfeita = indicador is not None and avaliar_condicao(
                regra.condicoes, indicador.valor
            )
            if cotacao.data_hora >= corte and satisfeita and not satisfeita_anterior:
                ocorrencias.append(i)
            satisfeita_anterior = satisfeita

        retornos: dict[int, list[Decimal]] = {5: [], 20: [], 60: []}
        for i in ocorrencias:
            preco_base = cotacoes[i].fechamento
            for janela in (5, 20, 60):
                if i + janela < len(cotacoes):
                    preco_futuro = cotacoes[i + janela].fechamento
                    retornos[janela].append((preco_futuro / preco_base - 1) * 100)

        def _media(valores: list[Decimal]) -> Decimal | None:
            return sum(valores) / len(valores) if valores else None

        return ResultadoBacktest(
            regra_id=regra.id,
            ativo_id=ativo.id,
            total_ocorrencias=len(ocorrencias),
            retorno_medio_5_pregoes=_media(retornos[5]),
            retorno_medio_20_pregoes=_media(retornos[20]),
            retorno_medio_60_pregoes=_media(retornos[60]),
        )
```

- [ ] **Step 4: Rodar e confirmar GREEN**

```bash
.venv/bin/python -m pytest tests/unit/services/test_sinal_service.py -q
```

Esperado: `16 passed`.

- [ ] **Step 5: Rodar `ruff check` e a suíte completa**

```bash
.venv/bin/ruff check src/ tests/
.venv/bin/python -m pytest -q
```

Esperado: lint limpo, todos os testes passando.

- [ ] **Step 6: Commit**

```bash
git add src/app/services/sinal_service.py tests/unit/services/test_sinal_service.py
git commit -m "feat(sinais): adiciona SinalService.backtest"
```

---

## Task 6: Endpoints `GET /ativos/{id}/sinais` e `GET /ativos/{id}/sinais/{regra_id}/backtest`

**Files:**
- Create: `src/app/api/v1/schemas/sinal.py`
- Modify: `src/app/api/v1/controllers/ativos.py`
- Modify: `src/app/api/deps.py`
- Modify: `tests/unit/api/conftest.py`
- Test: `tests/unit/api/test_sinal_controller.py`

**Interfaces:**
- Consumes: `SinalService.avaliar_ativo`/`.backtest` (Tasks 4/5), `buscar_regra_por_id` (Task 1), `AtivoNaoEncontradoError`, `RegraNaoEncontradaError`
- Produces: endpoints HTTP `GET /ativos/{ativo_id}/sinais` e `GET /ativos/{ativo_id}/sinais/{regra_id}/backtest`.

- [ ] **Step 1: Criar o schema de resposta**

Arquivo `src/app/api/v1/schemas/sinal.py`:

```python
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from app.domain.entities.regra_sinal import RegraSinal
from app.domain.entities.sinal import Sinal
from app.domain.value_objects.resultado_backtest import ResultadoBacktest


class SinalResponse(BaseModel):
    id: UUID
    ativo_id: UUID
    regra_id: UUID
    regra_nome: str
    regra_descricao: str
    data_ativacao: datetime
    contexto: dict
    data_desativacao: datetime | None

    @staticmethod
    def de(sinal: Sinal, regra: RegraSinal) -> "SinalResponse":
        return SinalResponse(
            id=sinal.id,
            ativo_id=sinal.ativo_id,
            regra_id=sinal.regra_id,
            regra_nome=regra.nome,
            regra_descricao=regra.descricao,
            data_ativacao=sinal.data_ativacao,
            contexto=sinal.contexto,
            data_desativacao=sinal.data_desativacao,
        )


class ResultadoBacktestResponse(BaseModel):
    regra_id: UUID
    ativo_id: UUID
    total_ocorrencias: int
    retorno_medio_5_pregoes: Decimal | None
    retorno_medio_20_pregoes: Decimal | None
    retorno_medio_60_pregoes: Decimal | None

    @staticmethod
    def de(resultado: ResultadoBacktest) -> "ResultadoBacktestResponse":
        return ResultadoBacktestResponse(
            regra_id=resultado.regra_id,
            ativo_id=resultado.ativo_id,
            total_ocorrencias=resultado.total_ocorrencias,
            retorno_medio_5_pregoes=resultado.retorno_medio_5_pregoes,
            retorno_medio_20_pregoes=resultado.retorno_medio_20_pregoes,
            retorno_medio_60_pregoes=resultado.retorno_medio_60_pregoes,
        )
```

- [ ] **Step 2: Adicionar `get_sinal_repository` e `get_sinal_service` em `api/deps.py`**

No topo, junto aos imports existentes (ordem alfabética):

```python
from app.repositories.interfaces.sinal_repository import SinalRepository
from app.repositories.sqlalchemy.sinal_repository import SqlAlchemySinalRepository
from app.services.sinal_service import SinalService
```

Depois de `get_indicador_tecnico_repository`:

```python
def get_sinal_repository(
    session: Session = Depends(get_db_session),
) -> SinalRepository:
    return SqlAlchemySinalRepository(session)
```

Depois de `get_indicador_service`:

```python
def get_sinal_service(
    ativo_repository: AtivoRepository = Depends(get_ativo_repository),
    cotacao_repository: CotacaoRepository = Depends(get_cotacao_repository),
    indicador_service: IndicadorService = Depends(get_indicador_service),
    sinal_repository: SinalRepository = Depends(get_sinal_repository),
) -> SinalService:
    return SinalService(ativo_repository, cotacao_repository, indicador_service, sinal_repository)
```

- [ ] **Step 3: Adicionar o fixture e override em `tests/unit/api/conftest.py`**

No topo, adicionar aos imports existentes:

```python
from app.api.deps import get_sinal_repository
from tests.fixtures.fake_sinal_repository import FakeSinalRepository
```

(junto às linhas já existentes de `from app.api.deps import (...)` e `from tests.fixtures...`)

Adicionar o fixture, ao lado de `indicador_repository`:

```python
@pytest.fixture
def sinal_repository() -> FakeSinalRepository:
    return FakeSinalRepository()
```

No `client` fixture, adicionar o parâmetro e o override:

```python
def client(
    usuario_repository: FakeUsuarioRepository,
    ativo_repository: FakeAtivoRepository,
    watchlist_repository: FakeWatchlistRepository,
    dados_mercado_service: FakeDadosMercadoService,
    cotacao_repository: FakeCotacaoRepository,
    indicador_repository: FakeIndicadorTecnicoRepository,
    sinal_repository: FakeSinalRepository,
) -> TestClient:
    app.dependency_overrides[get_usuario_repository] = lambda: usuario_repository
    app.dependency_overrides[get_ativo_repository] = lambda: ativo_repository
    app.dependency_overrides[get_watchlist_repository] = lambda: watchlist_repository
    app.dependency_overrides[get_dados_mercado_service] = lambda: dados_mercado_service
    app.dependency_overrides[get_cotacao_repository] = lambda: cotacao_repository
    app.dependency_overrides[get_indicador_tecnico_repository] = lambda: indicador_repository
    app.dependency_overrides[get_sinal_repository] = lambda: sinal_repository
```

(mantendo o `with TestClient(app) as test_client: ...` que já vem depois)

- [ ] **Step 4: Escrever o teste dos endpoints (RED)**

Arquivo `tests/unit/api/test_sinal_controller.py`:

```python
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from app.domain.entities.ativo import Ativo
from app.domain.entities.cotacao import Cotacao
from app.domain.enums.tipo_ativo import TipoAtivo
from app.domain.regras_sinal_padrao import REGRAS_PADRAO

_PETR4 = Ativo(
    id=uuid4(),
    ticker="PETR4",
    nome="Petrobras PN",
    tipo=TipoAtivo.ACAO,
    setor="Petroleo e Gas",
    moeda="BRL",
    fonte_dados="brapi",
)

_REGRA_SOBREVENDA_RSI = next(r for r in REGRAS_PADRAO if r.nome == "Sobrevenda RSI")


def _cotacoes_rsi_baixo(ativo_id, dias: int) -> list[Cotacao]:
    precos = [20.0] * (dias - 10) + [20 - i * 1.0 for i in range(1, 11)]
    base = datetime.now(UTC) - timedelta(days=len(precos) - 1)
    return [
        Cotacao(
            id=uuid4(),
            ativo_id=ativo_id,
            data_hora=base + timedelta(days=i),
            abertura=Decimal(str(preco)),
            maxima=Decimal(str(preco)),
            minima=Decimal(str(preco)),
            fechamento=Decimal(str(preco)),
            volume=Decimal("1000000"),
        )
        for i, preco in enumerate(precos)
    ]


def test_sinais_sem_token_retorna_401(client, ativo_repository):
    ativo_repository.salvar(_PETR4)

    resposta = client.get(f"/api/v1/ativos/{_PETR4.id}/sinais")

    assert resposta.status_code == 401


def test_sinais_avalia_e_retorna_sinais_vigentes(client, auth_headers, ativo_repository, cotacao_repository):
    ativo_repository.salvar(_PETR4)
    cotacao_repository.salvar_muitas(_cotacoes_rsi_baixo(_PETR4.id, 40))

    resposta = client.get(f"/api/v1/ativos/{_PETR4.id}/sinais", headers=auth_headers)

    assert resposta.status_code == 200
    corpo = resposta.json()
    nomes = {item["regra_nome"] for item in corpo}
    assert "Sobrevenda RSI" in nomes


def test_sinais_de_ativo_inexistente_retorna_404(client, auth_headers):
    resposta = client.get(f"/api/v1/ativos/{uuid4()}/sinais", headers=auth_headers)

    assert resposta.status_code == 404


def test_backtest_retorna_resultado(client, auth_headers, ativo_repository, cotacao_repository):
    ativo_repository.salvar(_PETR4)
    cotacao_repository.salvar_muitas(_cotacoes_rsi_baixo(_PETR4.id, 40))

    resposta = client.get(
        f"/api/v1/ativos/{_PETR4.id}/sinais/{_REGRA_SOBREVENDA_RSI.id}/backtest",
        headers=auth_headers,
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["regra_id"] == str(_REGRA_SOBREVENDA_RSI.id)
    assert corpo["total_ocorrencias"] >= 1


def test_backtest_com_regra_inexistente_retorna_404(client, auth_headers, ativo_repository):
    ativo_repository.salvar(_PETR4)

    resposta = client.get(
        f"/api/v1/ativos/{_PETR4.id}/sinais/{uuid4()}/backtest",
        headers=auth_headers,
    )

    assert resposta.status_code == 404


def test_backtest_com_ativo_inexistente_retorna_404(client, auth_headers):
    resposta = client.get(
        f"/api/v1/ativos/{uuid4()}/sinais/{_REGRA_SOBREVENDA_RSI.id}/backtest",
        headers=auth_headers,
    )

    assert resposta.status_code == 404
```

- [ ] **Step 5: Rodar e confirmar RED**

```bash
.venv/bin/python -m pytest tests/unit/api/test_sinal_controller.py -q
```

Esperado: falha com `404` nas rotas `/sinais`/`/sinais/.../backtest` (rotas ainda não existem) — confirmar que a falha é por rota ausente, não erro de digitação.

- [ ] **Step 6: Adicionar os endpoints em `src/app/api/v1/controllers/ativos.py`**

Ajustar o bloco de imports no topo do arquivo:

```python
from app.api.deps import (
    get_ativo_service,
    get_dados_mercado_service,
    get_indicador_service,
    get_sinal_service,
    get_usuario_atual,
)
from app.api.v1.schemas.ativo import AtivoEncontradoResponse
from app.api.v1.schemas.cotacao import CotacaoAtualResponse, PontoHistoricoResponse
from app.api.v1.schemas.indicador import IndicadorTecnicoResponse
from app.api.v1.schemas.sinal import ResultadoBacktestResponse, SinalResponse
from app.domain.entities.usuario import Usuario
from app.domain.enums.periodo_historico import PeriodoHistorico
from app.domain.regras_sinal_padrao import buscar_regra_por_id
from app.integrations.brapi.client import BrapiIndisponivelError, TickerNaoEncontradoError
from app.services.ativo_service import AtivoService
from app.services.dados_mercado_service import DadosMercadoService
from app.services.exceptions import AtivoNaoEncontradoError, RegraNaoEncontradaError
from app.services.indicador_service import IndicadorService
from app.services.sinal_service import SinalService
```

No final do arquivo, adicionar os dois novos endpoints:

```python
@router.get("/{ativo_id}/sinais", response_model=list[SinalResponse])
def sinais(
    ativo_id: UUID,
    usuario: Usuario = Depends(get_usuario_atual),
    service: SinalService = Depends(get_sinal_service),
) -> list[SinalResponse]:
    try:
        vigentes = service.avaliar_ativo(ativo_id)
    except AtivoNaoEncontradoError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ativo nao encontrado") from exc

    return [SinalResponse.de(sinal, buscar_regra_por_id(sinal.regra_id)) for sinal in vigentes]


@router.get("/{ativo_id}/sinais/{regra_id}/backtest", response_model=ResultadoBacktestResponse)
def sinal_backtest(
    ativo_id: UUID,
    regra_id: UUID,
    usuario: Usuario = Depends(get_usuario_atual),
    service: SinalService = Depends(get_sinal_service),
) -> ResultadoBacktestResponse:
    try:
        resultado = service.backtest(regra_id, ativo_id)
    except AtivoNaoEncontradoError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ativo nao encontrado") from exc
    except RegraNaoEncontradaError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Regra nao encontrada") from exc

    return ResultadoBacktestResponse.de(resultado)
```

- [ ] **Step 7: Rodar e confirmar GREEN**

```bash
.venv/bin/python -m pytest tests/unit/api/test_sinal_controller.py -q
```

Esperado: `6 passed`.

- [ ] **Step 8: Rodar `ruff check` e a suíte completa**

```bash
.venv/bin/ruff check src/ tests/
.venv/bin/python -m pytest -q
```

Esperado: lint limpo, todos os testes passando (unitários + integração, com Postgres do docker-compose no ar).

- [ ] **Step 9: Commit**

```bash
git add src/app/api/v1/schemas/sinal.py src/app/api/v1/controllers/ativos.py src/app/api/deps.py tests/unit/api/conftest.py tests/unit/api/test_sinal_controller.py
git commit -m "feat(sinais): adiciona endpoints GET /ativos/{id}/sinais e backtest"
```

---

## Ao final de todas as tasks

Rodar a suíte completa uma última vez e revisar o diff inteiro:

```bash
.venv/bin/ruff check src/ tests/
.venv/bin/python -m pytest -q
git log --oneline develop..HEAD
git diff develop..HEAD --stat
```

Nenhuma mudança em `indicadores_tecnicos`, `cotacoes`, `Scheduler` ou fora do escopo descrito na spec. Nenhum CRUD de regras via API — `REGRAS_PADRAO` continua hardcoded.
