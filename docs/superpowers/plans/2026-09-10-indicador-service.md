# IndicadorService Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar o motor de cálculo de indicadores técnicos (SMA, RSI, MACD, Bollinger, Volume Relativo) sobre o histórico diário de cotações, persistir o valor mais recente de cada um por ativo, e expor um endpoint pra disparar o cálculo e consultar o resultado.

**Architecture:** Segue exatamente o padrão em camadas já estabelecido pra `Ativo`/`Cotacao`: entidade de domínio (já existe) → model SQLAlchemy + migration → repository (interface + impl, upsert) → service (métodos de cálculo puros + orquestração) → controller/endpoint, com injeção de dependência via `api/deps.py`. Os métodos de cálculo usam `pandas-ta` internamente mas recebem e devolvem apenas tipos de domínio (`Cotacao`, `IndicadorTecnico`) — nenhum código fora do service conhece pandas/pandas-ta.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 (estilo `Mapped`/`mapped_column`), Alembic, pandas + pandas-ta, pytest.

**Spec:** `docs/superpowers/specs/2026-09-10-indicador-service-design.md`

## Global Constraints

- Persistência é sempre upsert por `(ativo_id, chave)` — nunca guarda série histórica de cálculos, só o valor mais recente (decisão da spec).
- Histórico insuficiente pra um indicador nunca lança exceção — o método de cálculo retorna `None` e `calcular_todos` simplesmente omite esse indicador do resultado.
- `parametros` de cada indicador é sempre construído na mesma ordem de chaves (ver tabela na spec) pra `chave` ficar determinística: `chave = f"{tipo.value}_" + "_".join(str(v) for v in parametros.values())`.
- `calcular_todos` recebe `ativo_id: UUID` (não o objeto `Ativo` do diagrama UML da doc técnica) — resolve o `Ativo` internamente, mesmo padrão de `AtivoService`/`WatchlistService`.
- Nenhuma mudança em `cotacoes`, no `Scheduler` (não existe ainda) ou em `SinalService` (item futuro) — fora de escopo.

---

## Task 1: `IndicadorTecnicoModel` e migration

**Files:**
- Create: `src/app/db/models/indicador_tecnico.py`
- Create: `alembic/versions/b8c1d3e9f2a7_cria_tabela_indicadores_tecnicos.py`
- Modify: `alembic/env.py` (adicionar import do model, mesmo padrão de `CotacaoModel`)
- Modify: `tests/integration/conftest.py` (adicionar import do model, mesmo padrão de `CotacaoModel`)

**Interfaces:**
- Consumes: nada (primeira peça da feature)
- Produces: `IndicadorTecnicoModel` (tabela `indicadores_tecnicos`, colunas `id`, `ativo_id`, `tipo`, `parametros`, `chave`, `data_calculo`, `valor`, `valores_auxiliares`, unique constraint `(ativo_id, chave)`) — usado pelo repository na Task 2.

- [ ] **Step 1: Criar o model**

Arquivo `src/app/db/models/indicador_tecnico.py`:

```python
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Numeric, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class IndicadorTecnicoModel(Base):
    __tablename__ = "indicadores_tecnicos"
    __table_args__ = (UniqueConstraint("ativo_id", "chave"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    ativo_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("ativos.id"), nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    parametros: Mapped[dict] = mapped_column(JSON, nullable=False)
    chave: Mapped[str] = mapped_column(String(50), nullable=False)
    data_calculo: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valor: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    valores_auxiliares: Mapped[dict | None] = mapped_column(JSON, nullable=True)
```

- [ ] **Step 2: Registrar o model no `alembic/env.py`**

Em `alembic/env.py`, ao lado dos outros imports de model:

```python
from app.db.models.indicador_tecnico import IndicadorTecnicoModel
```

(ordem alfabética junto com os outros `from app.db.models...`)

- [ ] **Step 3: Registrar o model no `tests/integration/conftest.py`**

Mesmo padrão — adicionar:

```python
from app.db.models.indicador_tecnico import IndicadorTecnicoModel
```

junto aos outros imports de model no topo do arquivo (ordem alfabética).

- [ ] **Step 4: Criar a migration**

Rodar pra confirmar qual é o head atual:

```bash
DATABASE_URL="postgresql://insightflow:insightflow@localhost:5432/insightflow" .venv/bin/alembic heads
```

Deve mostrar `a3f7c9e21d84` como head. Criar o arquivo `alembic/versions/b8c1d3e9f2a7_cria_tabela_indicadores_tecnicos.py`:

```python
"""cria tabela indicadores_tecnicos

Revision ID: b8c1d3e9f2a7
Revises: a3f7c9e21d84
Create Date: 2026-09-10 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b8c1d3e9f2a7"
down_revision: str | Sequence[str] | None = "a3f7c9e21d84"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "indicadores_tecnicos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ativo_id", sa.Uuid(), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("parametros", sa.JSON(), nullable=False),
        sa.Column("chave", sa.String(length=50), nullable=False),
        sa.Column("data_calculo", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valor", sa.Numeric(18, 6), nullable=False),
        sa.Column("valores_auxiliares", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(
            ["ativo_id"],
            ["ativos.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ativo_id", "chave"),
    )


def downgrade() -> None:
    op.drop_table("indicadores_tecnicos")
```

- [ ] **Step 5: Aplicar a migration e verificar upgrade/downgrade/upgrade**

```bash
DATABASE_URL="postgresql://insightflow:insightflow@localhost:5432/insightflow" .venv/bin/alembic upgrade head
DATABASE_URL="postgresql://insightflow:insightflow@localhost:5432/insightflow" .venv/bin/alembic downgrade -1
DATABASE_URL="postgresql://insightflow:insightflow@localhost:5432/insightflow" .venv/bin/alembic upgrade head
```

Todos os três comandos devem rodar sem erro (deve aparecer `Running upgrade a3f7c9e21d84 -> b8c1d3e9f2a7` etc).

- [ ] **Step 6: Rodar `ruff check` e a suíte completa pra garantir que nada quebrou**

```bash
.venv/bin/ruff check src/ tests/
.venv/bin/python -m pytest -q
```

Esperado: `All checks passed!` e todos os testes existentes passando (nenhum teste novo ainda nesta task).

- [ ] **Step 7: Commit**

```bash
git add src/app/db/models/indicador_tecnico.py alembic/versions/b8c1d3e9f2a7_cria_tabela_indicadores_tecnicos.py alembic/env.py tests/integration/conftest.py
git commit -m "feat(indicadores): cria tabela indicadores_tecnicos"
```

---

## Task 2: `IndicadorTecnicoRepository` (interface + SQLAlchemy) com teste de integração

**Files:**
- Create: `src/app/repositories/interfaces/indicador_tecnico_repository.py`
- Create: `src/app/repositories/sqlalchemy/indicador_tecnico_repository.py`
- Test: `tests/integration/repositories/test_indicador_tecnico_repository.py`

**Interfaces:**
- Consumes: `IndicadorTecnicoModel` (Task 1), `IndicadorTecnico` (`app.domain.entities.indicador_tecnico`, já existe), `TipoIndicador` (`app.domain.enums.tipo_indicador`, já existe)
- Produces: `IndicadorTecnicoRepository.salvar(indicador: IndicadorTecnico) -> None` e `IndicadorTecnicoRepository.listar_por_ativo(ativo_id: UUID) -> list[IndicadorTecnico]` — usados pelo `IndicadorService` (Task 5) e pelo fake (Task 3).

- [ ] **Step 1: Escrever o teste de integração (RED)**

Arquivo `tests/integration/repositories/test_indicador_tecnico_repository.py`:

```python
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.entities.ativo import Ativo
from app.domain.entities.indicador_tecnico import IndicadorTecnico
from app.domain.enums.tipo_ativo import TipoAtivo
from app.domain.enums.tipo_indicador import TipoIndicador
from app.repositories.sqlalchemy.ativo_repository import SqlAlchemyAtivoRepository
from app.repositories.sqlalchemy.indicador_tecnico_repository import (
    SqlAlchemyIndicadorTecnicoRepository,
)

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


def _indicador(ativo_id, tipo=TipoIndicador.SMA, periodo=20, valor="10.5") -> IndicadorTecnico:
    return IndicadorTecnico(
        id=uuid4(),
        ativo_id=ativo_id,
        tipo=tipo,
        parametros={"periodo": periodo},
        data_calculo=datetime(2024, 1, 1, tzinfo=UTC),
        valor=Decimal(valor),
        valores_auxiliares=None,
    )


def test_salvar_e_listar_por_ativo_retorna_o_indicador(session):
    ativo = _novo_ativo(session)
    repo = SqlAlchemyIndicadorTecnicoRepository(session)

    repo.salvar(_indicador(ativo.id))

    encontrados = repo.listar_por_ativo(ativo.id)
    assert len(encontrados) == 1
    assert encontrados[0].tipo == TipoIndicador.SMA
    assert encontrados[0].parametros == {"periodo": 20}
    assert encontrados[0].valor == Decimal("10.5")


def test_salvar_em_conflito_atualiza_em_vez_de_duplicar(session):
    ativo = _novo_ativo(session)
    repo = SqlAlchemyIndicadorTecnicoRepository(session)
    repo.salvar(_indicador(ativo.id, valor="10.5"))

    repo.salvar(_indicador(ativo.id, valor="11.0"))

    encontrados = repo.listar_por_ativo(ativo.id)
    assert len(encontrados) == 1
    assert encontrados[0].valor == Decimal("11.0")


def test_indicadores_com_parametros_diferentes_nao_se_sobrescrevem(session):
    ativo = _novo_ativo(session)
    repo = SqlAlchemyIndicadorTecnicoRepository(session)

    repo.salvar(_indicador(ativo.id, tipo=TipoIndicador.SMA, periodo=20, valor="10.5"))
    repo.salvar(_indicador(ativo.id, tipo=TipoIndicador.SMA, periodo=50, valor="9.0"))

    encontrados = repo.listar_por_ativo(ativo.id)
    assert len(encontrados) == 2
    valores = {i.parametros["periodo"]: i.valor for i in encontrados}
    assert valores == {20: Decimal("10.5"), 50: Decimal("9.0")}


def test_valores_auxiliares_persiste_e_retorna_o_dict(session):
    ativo = _novo_ativo(session)
    repo = SqlAlchemyIndicadorTecnicoRepository(session)
    indicador = IndicadorTecnico(
        id=uuid4(),
        ativo_id=ativo.id,
        tipo=TipoIndicador.MACD,
        parametros={"rapida": 12, "lenta": 26, "sinal": 9},
        data_calculo=datetime(2024, 1, 1, tzinfo=UTC),
        valor=Decimal("1.5"),
        valores_auxiliares={"linha_sinal": 1.2, "histograma": 0.3},
    )

    repo.salvar(indicador)

    encontrados = repo.listar_por_ativo(ativo.id)
    assert encontrados[0].valores_auxiliares == {"linha_sinal": 1.2, "histograma": 0.3}


def test_listar_por_ativo_sem_indicadores_retorna_lista_vazia(session):
    ativo = _novo_ativo(session)
    repo = SqlAlchemyIndicadorTecnicoRepository(session)

    assert repo.listar_por_ativo(ativo.id) == []
```

- [ ] **Step 2: Rodar o teste e confirmar que falha por módulo ausente**

```bash
docker compose up -d postgres
.venv/bin/python -m pytest tests/integration/repositories/test_indicador_tecnico_repository.py -q
```

Esperado: `ModuleNotFoundError: No module named 'app.repositories.interfaces.indicador_tecnico_repository'` (ou similar) — falha porque o código ainda não existe, não por erro de digitação.

- [ ] **Step 3: Criar a interface**

Arquivo `src/app/repositories/interfaces/indicador_tecnico_repository.py`:

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.indicador_tecnico import IndicadorTecnico


class IndicadorTecnicoRepository(ABC):
    @abstractmethod
    def salvar(self, indicador: IndicadorTecnico) -> None: ...

    @abstractmethod
    def listar_por_ativo(self, ativo_id: UUID) -> list[IndicadorTecnico]: ...
```

- [ ] **Step 4: Criar a implementação SQLAlchemy**

Arquivo `src/app/repositories/sqlalchemy/indicador_tecnico_repository.py`:

```python
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models.indicador_tecnico import IndicadorTecnicoModel
from app.domain.entities.indicador_tecnico import IndicadorTecnico
from app.domain.enums.tipo_indicador import TipoIndicador
from app.repositories.interfaces.indicador_tecnico_repository import IndicadorTecnicoRepository


def _chave_de(tipo: TipoIndicador, parametros: dict) -> str:
    partes = "_".join(str(valor) for valor in parametros.values())
    return f"{tipo.value}_{partes}"


class SqlAlchemyIndicadorTecnicoRepository(IndicadorTecnicoRepository):
    def __init__(self, session: Session):
        self._session = session

    def salvar(self, indicador: IndicadorTecnico) -> None:
        chave = _chave_de(indicador.tipo, indicador.parametros)
        stmt = insert(IndicadorTecnicoModel).values(
            id=indicador.id,
            ativo_id=indicador.ativo_id,
            tipo=indicador.tipo.value,
            parametros=indicador.parametros,
            chave=chave,
            data_calculo=indicador.data_calculo,
            valor=indicador.valor,
            valores_auxiliares=indicador.valores_auxiliares,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["ativo_id", "chave"],
            set_={
                "parametros": stmt.excluded.parametros,
                "data_calculo": stmt.excluded.data_calculo,
                "valor": stmt.excluded.valor,
                "valores_auxiliares": stmt.excluded.valores_auxiliares,
            },
        )
        self._session.execute(stmt)
        self._session.commit()

    def listar_por_ativo(self, ativo_id: UUID) -> list[IndicadorTecnico]:
        modelos = self._session.scalars(
            select(IndicadorTecnicoModel).where(IndicadorTecnicoModel.ativo_id == ativo_id)
        )
        return [self._para_entidade(modelo) for modelo in modelos]

    @staticmethod
    def _para_entidade(modelo: IndicadorTecnicoModel) -> IndicadorTecnico:
        return IndicadorTecnico(
            id=modelo.id,
            ativo_id=modelo.ativo_id,
            tipo=TipoIndicador(modelo.tipo),
            parametros=modelo.parametros,
            data_calculo=modelo.data_calculo,
            valor=modelo.valor,
            valores_auxiliares=modelo.valores_auxiliares,
        )
```

- [ ] **Step 5: Rodar o teste e confirmar que passa (GREEN)**

```bash
.venv/bin/python -m pytest tests/integration/repositories/test_indicador_tecnico_repository.py -q
```

Esperado: `5 passed`.

- [ ] **Step 6: Rodar `ruff check` e a suíte completa**

```bash
.venv/bin/ruff check src/ tests/
.venv/bin/python -m pytest -q
```

Esperado: lint limpo, todos os testes passando.

- [ ] **Step 7: Commit**

```bash
git add src/app/repositories/interfaces/indicador_tecnico_repository.py src/app/repositories/sqlalchemy/indicador_tecnico_repository.py tests/integration/repositories/test_indicador_tecnico_repository.py
git commit -m "feat(indicadores): adiciona IndicadorTecnicoRepository com upsert por ativo+chave"
```

---

## Task 3: `FakeIndicadorTecnicoRepository`

**Files:**
- Create: `tests/fixtures/fake_indicador_tecnico_repository.py`

**Interfaces:**
- Consumes: `IndicadorTecnicoRepository` (Task 2)
- Produces: `FakeIndicadorTecnicoRepository` — usado pelos testes unitários do `IndicadorService` (Task 5) e do controller (Task 6).

Esta task não tem ciclo RED/GREEN próprio — é um fixture de teste sem lógica de negócio (mesmo espírito de `FakeCotacaoRepository`, que também não tem teste dedicado). Implementa direto e valida via uso nas próximas tasks.

- [ ] **Step 1: Criar o fake**

Arquivo `tests/fixtures/fake_indicador_tecnico_repository.py`:

```python
from __future__ import annotations

from uuid import UUID

from app.domain.entities.indicador_tecnico import IndicadorTecnico
from app.repositories.interfaces.indicador_tecnico_repository import IndicadorTecnicoRepository


class FakeIndicadorTecnicoRepository(IndicadorTecnicoRepository):
    def __init__(self) -> None:
        self._indicadores: dict[tuple, IndicadorTecnico] = {}

    def salvar(self, indicador: IndicadorTecnico) -> None:
        chave = (indicador.ativo_id, indicador.tipo, tuple(indicador.parametros.values()))
        self._indicadores[chave] = indicador

    def listar_por_ativo(self, ativo_id: UUID) -> list[IndicadorTecnico]:
        return [i for i in self._indicadores.values() if i.ativo_id == ativo_id]
```

- [ ] **Step 2: Rodar `ruff check`**

```bash
.venv/bin/ruff check tests/fixtures/fake_indicador_tecnico_repository.py
```

Esperado: `All checks passed!`

- [ ] **Step 3: Commit**

```bash
git add tests/fixtures/fake_indicador_tecnico_repository.py
git commit -m "test(indicadores): adiciona FakeIndicadorTecnicoRepository"
```

---

## Task 4: Métodos de cálculo puros do `IndicadorService`

**Files:**
- Create: `src/app/services/indicador_service.py`
- Test: `tests/unit/services/test_indicador_service.py`

**Interfaces:**
- Consumes: `Cotacao` (`app.domain.entities.cotacao`, já existe), `IndicadorTecnico`, `TipoIndicador`, `pandas`, `pandas_ta`
- Produces: `IndicadorService.calcular_sma(cotacoes, periodo) -> IndicadorTecnico | None`, `.calcular_rsi(cotacoes, periodo=14) -> IndicadorTecnico | None`, `.calcular_macd(cotacoes, rapida=12, lenta=26, sinal=9) -> IndicadorTecnico | None`, `.calcular_bollinger(cotacoes, periodo=20, desvios=2) -> IndicadorTecnico | None`, `.calcular_volume_relativo(cotacoes, periodo=20) -> IndicadorTecnico | None` — usados por `calcular_todos` (Task 5).

Nota: `IndicadorService.__init__` já recebe os três repositórios (`ativo_repository`, `cotacao_repository`, `indicador_repository`) desde este task, mas eles só são usados a partir da Task 5 — os métodos de cálculo abaixo não tocam em nenhum repositório, só recebem `list[Cotacao]` diretamente.

- [ ] **Step 1: Escrever o helper de teste e os testes de SMA (RED)**

Arquivo `tests/unit/services/test_indicador_service.py`:

```python
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from app.domain.entities.cotacao import Cotacao
from app.domain.enums.tipo_indicador import TipoIndicador
from app.services.indicador_service import IndicadorService
from tests.fixtures.fake_ativo_repository import FakeAtivoRepository
from tests.fixtures.fake_cotacao_repository import FakeCotacaoRepository
from tests.fixtures.fake_indicador_tecnico_repository import FakeIndicadorTecnicoRepository

_ATIVO_ID = uuid4()


def _cotacoes(fechamentos: list[str], volumes: list[str] | None = None) -> list[Cotacao]:
    volumes = volumes or ["1000000"] * len(fechamentos)
    base = datetime(2024, 1, 1, tzinfo=UTC)
    return [
        Cotacao(
            id=uuid4(),
            ativo_id=_ATIVO_ID,
            data_hora=base + timedelta(days=i),
            abertura=Decimal(fechamento),
            maxima=Decimal(fechamento),
            minima=Decimal(fechamento),
            fechamento=Decimal(fechamento),
            volume=Decimal(volume),
        )
        for i, (fechamento, volume) in enumerate(zip(fechamentos, volumes, strict=True))
    ]


def _service() -> IndicadorService:
    return IndicadorService(
        FakeAtivoRepository(), FakeCotacaoRepository(), FakeIndicadorTecnicoRepository()
    )


def test_calcular_sma_com_precos_constantes_retorna_o_proprio_preco():
    cotacoes = _cotacoes(["10"] * 20)
    service = _service()

    indicador = service.calcular_sma(cotacoes, periodo=20)

    assert indicador is not None
    assert indicador.ativo_id == _ATIVO_ID
    assert indicador.tipo == TipoIndicador.SMA
    assert indicador.parametros == {"periodo": 20}
    assert indicador.valor == Decimal("10")
    assert indicador.valores_auxiliares is None


def test_calcular_sma_com_historico_insuficiente_retorna_none():
    cotacoes = _cotacoes(["10", "11", "12"])
    service = _service()

    assert service.calcular_sma(cotacoes, periodo=20) is None


def test_calcular_sma_com_lista_vazia_retorna_none():
    service = _service()

    assert service.calcular_sma([], periodo=20) is None
```

- [ ] **Step 2: Rodar e confirmar RED**

```bash
.venv/bin/python -m pytest tests/unit/services/test_indicador_service.py -q
```

Esperado: `ModuleNotFoundError: No module named 'app.services.indicador_service'`.

- [ ] **Step 3: Criar o service com `__init__` e `calcular_sma`**

Arquivo `src/app/services/indicador_service.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pandas as pd
import pandas_ta as ta

from app.domain.entities.ativo import Ativo
from app.domain.entities.cotacao import Cotacao
from app.domain.entities.indicador_tecnico import IndicadorTecnico
from app.domain.enums.tipo_indicador import TipoIndicador
from app.repositories.interfaces.ativo_repository import AtivoRepository
from app.repositories.interfaces.cotacao_repository import CotacaoRepository
from app.repositories.interfaces.indicador_tecnico_repository import IndicadorTecnicoRepository
from app.services.exceptions import AtivoNaoEncontradoError


class IndicadorService:
    def __init__(
        self,
        ativo_repository: AtivoRepository,
        cotacao_repository: CotacaoRepository,
        indicador_repository: IndicadorTecnicoRepository,
    ):
        self._ativo_repository = ativo_repository
        self._cotacao_repository = cotacao_repository
        self._indicador_repository = indicador_repository

    def calcular_sma(self, cotacoes: list[Cotacao], periodo: int) -> IndicadorTecnico | None:
        if not cotacoes:
            return None
        fechamentos = pd.Series([float(c.fechamento) for c in cotacoes])
        resultado = ta.sma(fechamentos, length=periodo)
        if resultado is None or pd.isna(resultado.iloc[-1]):
            return None
        return IndicadorTecnico(
            id=uuid4(),
            ativo_id=cotacoes[0].ativo_id,
            tipo=TipoIndicador.SMA,
            parametros={"periodo": periodo},
            data_calculo=datetime.now(UTC),
            valor=Decimal(str(resultado.iloc[-1])),
            valores_auxiliares=None,
        )

    def _buscar_ativo(self, ativo_id: UUID) -> Ativo:
        ativo = self._ativo_repository.buscar_por_id(ativo_id)
        if ativo is None:
            raise AtivoNaoEncontradoError(ativo_id)
        return ativo
```

- [ ] **Step 4: Rodar e confirmar GREEN**

```bash
.venv/bin/python -m pytest tests/unit/services/test_indicador_service.py -q
```

Esperado: `3 passed`.

- [ ] **Step 5: Escrever os testes de RSI (RED)**

Adicionar em `tests/unit/services/test_indicador_service.py`:

```python
def test_calcular_rsi_com_precos_constantes_retorna_indicador_valido():
    cotacoes = _cotacoes(["10"] * 20)
    service = _service()

    indicador = service.calcular_rsi(cotacoes, periodo=14)

    assert indicador is not None
    assert indicador.tipo == TipoIndicador.RSI
    assert indicador.parametros == {"periodo": 14}
    assert Decimal("0") <= indicador.valor <= Decimal("100")


def test_calcular_rsi_com_historico_insuficiente_retorna_none():
    cotacoes = _cotacoes(["10", "11", "12"])
    service = _service()

    assert service.calcular_rsi(cotacoes, periodo=14) is None
```

- [ ] **Step 6: Rodar e confirmar RED**

```bash
.venv/bin/python -m pytest tests/unit/services/test_indicador_service.py -q -k rsi
```

Esperado: `AttributeError: 'IndicadorService' object has no attribute 'calcular_rsi'`.

- [ ] **Step 7: Implementar `calcular_rsi`**

Adicionar em `src/app/services/indicador_service.py`, logo após `calcular_sma`:

```python
    def calcular_rsi(self, cotacoes: list[Cotacao], periodo: int = 14) -> IndicadorTecnico | None:
        if not cotacoes:
            return None
        fechamentos = pd.Series([float(c.fechamento) for c in cotacoes])
        resultado = ta.rsi(fechamentos, length=periodo)
        if resultado is None or pd.isna(resultado.iloc[-1]):
            return None
        return IndicadorTecnico(
            id=uuid4(),
            ativo_id=cotacoes[0].ativo_id,
            tipo=TipoIndicador.RSI,
            parametros={"periodo": periodo},
            data_calculo=datetime.now(UTC),
            valor=Decimal(str(resultado.iloc[-1])),
            valores_auxiliares=None,
        )
```

- [ ] **Step 8: Rodar e confirmar GREEN**

```bash
.venv/bin/python -m pytest tests/unit/services/test_indicador_service.py -q -k rsi
```

Esperado: `2 passed`.

- [ ] **Step 9: Escrever os testes de MACD (RED)**

Adicionar em `tests/unit/services/test_indicador_service.py`:

```python
def test_calcular_macd_com_historico_suficiente_retorna_indicador_com_auxiliares():
    fechamentos = [str(10 + i * 0.1) for i in range(60)]
    cotacoes = _cotacoes(fechamentos)
    service = _service()

    indicador = service.calcular_macd(cotacoes)

    assert indicador is not None
    assert indicador.tipo == TipoIndicador.MACD
    assert indicador.parametros == {"rapida": 12, "lenta": 26, "sinal": 9}
    assert indicador.valores_auxiliares is not None
    assert "linha_sinal" in indicador.valores_auxiliares
    assert "histograma" in indicador.valores_auxiliares


def test_calcular_macd_com_historico_insuficiente_retorna_none():
    cotacoes = _cotacoes(["10"] * 5)
    service = _service()

    assert service.calcular_macd(cotacoes) is None
```

- [ ] **Step 10: Rodar e confirmar RED**

```bash
.venv/bin/python -m pytest tests/unit/services/test_indicador_service.py -q -k macd
```

Esperado: `AttributeError: 'IndicadorService' object has no attribute 'calcular_macd'`.

- [ ] **Step 11: Implementar `calcular_macd`**

Adicionar em `src/app/services/indicador_service.py`, logo após `calcular_rsi`:

```python
    def calcular_macd(
        self, cotacoes: list[Cotacao], rapida: int = 12, lenta: int = 26, sinal: int = 9
    ) -> IndicadorTecnico | None:
        if not cotacoes:
            return None
        fechamentos = pd.Series([float(c.fechamento) for c in cotacoes])
        resultado = ta.macd(fechamentos, fast=rapida, slow=lenta, signal=sinal)
        if resultado is None:
            return None
        linha_macd = resultado.iloc[-1, 0]
        linha_histograma = resultado.iloc[-1, 1]
        linha_sinal = resultado.iloc[-1, 2]
        if pd.isna(linha_macd) or pd.isna(linha_histograma) or pd.isna(linha_sinal):
            return None
        return IndicadorTecnico(
            id=uuid4(),
            ativo_id=cotacoes[0].ativo_id,
            tipo=TipoIndicador.MACD,
            parametros={"rapida": rapida, "lenta": lenta, "sinal": sinal},
            data_calculo=datetime.now(UTC),
            valor=Decimal(str(linha_macd)),
            valores_auxiliares={
                "linha_sinal": float(linha_sinal),
                "histograma": float(linha_histograma),
            },
        )
```

- [ ] **Step 12: Rodar e confirmar GREEN**

```bash
.venv/bin/python -m pytest tests/unit/services/test_indicador_service.py -q -k macd
```

Esperado: `2 passed`.

- [ ] **Step 13: Escrever os testes de Bollinger (RED)**

Adicionar em `tests/unit/services/test_indicador_service.py`:

```python
def test_calcular_bollinger_com_precos_constantes_bandas_iguais_ao_preco():
    cotacoes = _cotacoes(["10"] * 20)
    service = _service()

    indicador = service.calcular_bollinger(cotacoes, periodo=20, desvios=2)

    assert indicador is not None
    assert indicador.tipo == TipoIndicador.BOLLINGER
    assert indicador.parametros == {"periodo": 20, "desvios": 2}
    assert indicador.valor == Decimal("10")
    assert indicador.valores_auxiliares == {"banda_superior": 10.0, "banda_inferior": 10.0}


def test_calcular_bollinger_com_historico_insuficiente_retorna_none():
    cotacoes = _cotacoes(["10", "11", "12"])
    service = _service()

    assert service.calcular_bollinger(cotacoes, periodo=20, desvios=2) is None
```

- [ ] **Step 14: Rodar e confirmar RED**

```bash
.venv/bin/python -m pytest tests/unit/services/test_indicador_service.py -q -k bollinger
```

Esperado: `AttributeError: 'IndicadorService' object has no attribute 'calcular_bollinger'`.

- [ ] **Step 15: Implementar `calcular_bollinger`**

Adicionar em `src/app/services/indicador_service.py`, logo após `calcular_macd`:

```python
    def calcular_bollinger(
        self, cotacoes: list[Cotacao], periodo: int = 20, desvios: float = 2
    ) -> IndicadorTecnico | None:
        if not cotacoes:
            return None
        fechamentos = pd.Series([float(c.fechamento) for c in cotacoes])
        resultado = ta.bbands(fechamentos, length=periodo, std=desvios)
        if resultado is None:
            return None
        banda_inferior = resultado.iloc[-1, 0]
        banda_media = resultado.iloc[-1, 1]
        banda_superior = resultado.iloc[-1, 2]
        if pd.isna(banda_inferior) or pd.isna(banda_media) or pd.isna(banda_superior):
            return None
        return IndicadorTecnico(
            id=uuid4(),
            ativo_id=cotacoes[0].ativo_id,
            tipo=TipoIndicador.BOLLINGER,
            parametros={"periodo": periodo, "desvios": desvios},
            data_calculo=datetime.now(UTC),
            valor=Decimal(str(banda_media)),
            valores_auxiliares={
                "banda_superior": float(banda_superior),
                "banda_inferior": float(banda_inferior),
            },
        )
```

- [ ] **Step 16: Rodar e confirmar GREEN**

```bash
.venv/bin/python -m pytest tests/unit/services/test_indicador_service.py -q -k bollinger
```

Esperado: `2 passed`.

- [ ] **Step 17: Escrever os testes de Volume Relativo (RED)**

Adicionar em `tests/unit/services/test_indicador_service.py`:

```python
def test_calcular_volume_relativo_com_volume_constante_retorna_um():
    cotacoes = _cotacoes(["10"] * 20, volumes=["500000"] * 20)
    service = _service()

    indicador = service.calcular_volume_relativo(cotacoes, periodo=20)

    assert indicador is not None
    assert indicador.tipo == TipoIndicador.VOLUME_RELATIVO
    assert indicador.parametros == {"periodo": 20}
    assert indicador.valor == Decimal("1")
    assert indicador.valores_auxiliares is None


def test_calcular_volume_relativo_com_historico_insuficiente_retorna_none():
    cotacoes = _cotacoes(["10", "11", "12"])
    service = _service()

    assert service.calcular_volume_relativo(cotacoes, periodo=20) is None
```

- [ ] **Step 18: Rodar e confirmar RED**

```bash
.venv/bin/python -m pytest tests/unit/services/test_indicador_service.py -q -k volume_relativo
```

Esperado: `AttributeError: 'IndicadorService' object has no attribute 'calcular_volume_relativo'`.

- [ ] **Step 19: Implementar `calcular_volume_relativo`**

Adicionar em `src/app/services/indicador_service.py`, logo após `calcular_bollinger`:

```python
    def calcular_volume_relativo(
        self, cotacoes: list[Cotacao], periodo: int = 20
    ) -> IndicadorTecnico | None:
        if not cotacoes:
            return None
        volumes = pd.Series([float(c.volume) for c in cotacoes])
        media = ta.sma(volumes, length=periodo)
        if media is None or pd.isna(media.iloc[-1]) or media.iloc[-1] == 0:
            return None
        razao = volumes.iloc[-1] / media.iloc[-1]
        return IndicadorTecnico(
            id=uuid4(),
            ativo_id=cotacoes[0].ativo_id,
            tipo=TipoIndicador.VOLUME_RELATIVO,
            parametros={"periodo": periodo},
            data_calculo=datetime.now(UTC),
            valor=Decimal(str(razao)),
            valores_auxiliares=None,
        )
```

- [ ] **Step 20: Rodar todos os testes do service e confirmar GREEN**

```bash
.venv/bin/python -m pytest tests/unit/services/test_indicador_service.py -q
```

Esperado: `13 passed`.

- [ ] **Step 21: Rodar `ruff check` e a suíte completa**

```bash
.venv/bin/ruff check src/ tests/
.venv/bin/python -m pytest -q
```

Esperado: lint limpo, todos os testes passando.

- [ ] **Step 22: Commit**

```bash
git add src/app/services/indicador_service.py tests/unit/services/test_indicador_service.py
git commit -m "feat(indicadores): adiciona metodos de calculo do IndicadorService (SMA, RSI, MACD, Bollinger, volume relativo)"
```

---

## Task 5: `IndicadorService.calcular_todos` (orquestração)

**Files:**
- Modify: `src/app/services/indicador_service.py`
- Modify: `tests/unit/services/test_indicador_service.py`

**Interfaces:**
- Consumes: os 5 métodos de cálculo (Task 4), `AtivoRepository.buscar_por_id`, `CotacaoRepository.listar_por_ativo`, `IndicadorTecnicoRepository.salvar` (Task 2), `AtivoNaoEncontradoError` (`app.services.exceptions`, já existe)
- Produces: `IndicadorService.calcular_todos(ativo_id: UUID) -> list[IndicadorTecnico]` — usado pelo endpoint (Task 6).

- [ ] **Step 1: Escrever os testes de `calcular_todos` (RED)**

Adicionar em `tests/unit/services/test_indicador_service.py`, no topo do arquivo importar o que falta:

```python
import pytest

from app.domain.entities.ativo import Ativo
from app.domain.enums.tipo_ativo import TipoAtivo
from app.services.exceptions import AtivoNaoEncontradoError
```

E ao final do arquivo:

```python
_PETR4 = Ativo(
    id=_ATIVO_ID,
    ticker="PETR4",
    nome="Petrobras PN",
    tipo=TipoAtivo.ACAO,
    setor="Petroleo e Gas",
    moeda="BRL",
    fonte_dados="manual",
)


def test_calcular_todos_persiste_e_retorna_os_indicadores_calculaveis():
    ativo_repository = FakeAtivoRepository()
    ativo_repository.salvar(_PETR4)
    cotacao_repository = FakeCotacaoRepository()
    cotacao_repository.salvar_muitas(_cotacoes([str(10 + i * 0.05) for i in range(60)]))
    indicador_repository = FakeIndicadorTecnicoRepository()
    service = IndicadorService(ativo_repository, cotacao_repository, indicador_repository)

    calculados = service.calcular_todos(_ATIVO_ID)

    tipos_calculados = {i.tipo for i in calculados}
    assert TipoIndicador.SMA in tipos_calculados
    assert TipoIndicador.RSI in tipos_calculados
    assert TipoIndicador.MACD in tipos_calculados
    assert TipoIndicador.BOLLINGER in tipos_calculados
    assert TipoIndicador.VOLUME_RELATIVO in tipos_calculados

    persistidos = indicador_repository.listar_por_ativo(_ATIVO_ID)
    assert len(persistidos) == len(calculados)


def test_calcular_todos_omite_sma_200_quando_historico_e_curto():
    ativo_repository = FakeAtivoRepository()
    ativo_repository.salvar(_PETR4)
    cotacao_repository = FakeCotacaoRepository()
    cotacao_repository.salvar_muitas(_cotacoes([str(10 + i * 0.05) for i in range(60)]))
    indicador_repository = FakeIndicadorTecnicoRepository()
    service = IndicadorService(ativo_repository, cotacao_repository, indicador_repository)

    calculados = service.calcular_todos(_ATIVO_ID)

    smas = [i for i in calculados if i.tipo == TipoIndicador.SMA]
    periodos = {i.parametros["periodo"] for i in smas}
    assert periodos == {20, 50}


def test_calcular_todos_com_ativo_inexistente_lanca_erro():
    service = IndicadorService(
        FakeAtivoRepository(), FakeCotacaoRepository(), FakeIndicadorTecnicoRepository()
    )

    with pytest.raises(AtivoNaoEncontradoError):
        service.calcular_todos(uuid4())
```

- [ ] **Step 2: Rodar e confirmar RED**

```bash
.venv/bin/python -m pytest tests/unit/services/test_indicador_service.py -q -k calcular_todos
```

Esperado: `AttributeError: 'IndicadorService' object has no attribute 'calcular_todos'`.

- [ ] **Step 3: Implementar `calcular_todos`**

Adicionar em `src/app/services/indicador_service.py`, logo após `calcular_volume_relativo` (antes de `_buscar_ativo`):

```python
    def calcular_todos(self, ativo_id: UUID) -> list[IndicadorTecnico]:
        ativo = self._buscar_ativo(ativo_id)
        cotacoes = self._cotacao_repository.listar_por_ativo(ativo.id)
        candidatos = [
            self.calcular_sma(cotacoes, 20),
            self.calcular_sma(cotacoes, 50),
            self.calcular_sma(cotacoes, 200),
            self.calcular_rsi(cotacoes),
            self.calcular_macd(cotacoes),
            self.calcular_bollinger(cotacoes),
            self.calcular_volume_relativo(cotacoes),
        ]
        calculados = [c for c in candidatos if c is not None]
        for indicador in calculados:
            self._indicador_repository.salvar(indicador)
        return calculados
```

- [ ] **Step 4: Rodar e confirmar GREEN**

```bash
.venv/bin/python -m pytest tests/unit/services/test_indicador_service.py -q
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
git add src/app/services/indicador_service.py tests/unit/services/test_indicador_service.py
git commit -m "feat(indicadores): adiciona IndicadorService.calcular_todos"
```

---

## Task 6: Endpoint `GET /ativos/{ativo_id}/indicadores`

**Files:**
- Create: `src/app/api/v1/schemas/indicador.py`
- Modify: `src/app/api/v1/controllers/ativos.py`
- Modify: `src/app/api/deps.py`
- Modify: `tests/unit/api/conftest.py`
- Test: `tests/unit/api/test_indicador_controller.py`

**Interfaces:**
- Consumes: `IndicadorService.calcular_todos` (Task 5), `IndicadorTecnicoRepository` (Task 2), `AtivoNaoEncontradoError`, padrão de `get_ativo_service`/`client` fixture já existentes
- Produces: endpoint HTTP `GET /ativos/{ativo_id}/indicadores` retornando `list[IndicadorTecnicoResponse]`.

- [ ] **Step 1: Criar o schema de resposta**

Arquivo `src/app/api/v1/schemas/indicador.py`:

```python
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.domain.entities.indicador_tecnico import IndicadorTecnico
from app.domain.enums.tipo_indicador import TipoIndicador


class IndicadorTecnicoResponse(BaseModel):
    tipo: TipoIndicador
    parametros: dict
    data_calculo: datetime
    valor: Decimal
    valores_auxiliares: dict | None

    @staticmethod
    def de(indicador: IndicadorTecnico) -> "IndicadorTecnicoResponse":
        return IndicadorTecnicoResponse(
            tipo=indicador.tipo,
            parametros=indicador.parametros,
            data_calculo=indicador.data_calculo,
            valor=indicador.valor,
            valores_auxiliares=indicador.valores_auxiliares,
        )
```

- [ ] **Step 2: Adicionar `get_indicador_tecnico_repository` e `get_indicador_service` em `api/deps.py`**

No topo do arquivo, junto aos outros imports de `repositories.interfaces`/`repositories.sqlalchemy`/`services` (ordem alfabética):

```python
from app.repositories.interfaces.indicador_tecnico_repository import IndicadorTecnicoRepository
from app.repositories.sqlalchemy.indicador_tecnico_repository import (
    SqlAlchemyIndicadorTecnicoRepository,
)
from app.services.indicador_service import IndicadorService
```

Depois de `get_cotacao_repository`:

```python
def get_indicador_tecnico_repository(
    session: Session = Depends(get_db_session),
) -> IndicadorTecnicoRepository:
    return SqlAlchemyIndicadorTecnicoRepository(session)
```

Depois de `get_ativo_service`:

```python
def get_indicador_service(
    ativo_repository: AtivoRepository = Depends(get_ativo_repository),
    cotacao_repository: CotacaoRepository = Depends(get_cotacao_repository),
    indicador_repository: IndicadorTecnicoRepository = Depends(get_indicador_tecnico_repository),
) -> IndicadorService:
    return IndicadorService(ativo_repository, cotacao_repository, indicador_repository)
```

- [ ] **Step 3: Adicionar o fixture e override em `tests/unit/api/conftest.py`**

No topo, adicionar aos imports existentes:

```python
from app.api.deps import get_indicador_tecnico_repository
from tests.fixtures.fake_indicador_tecnico_repository import FakeIndicadorTecnicoRepository
```

(junto às linhas já existentes de `from app.api.deps import (...)` e `from tests.fixtures...`)

Adicionar o fixture, ao lado de `cotacao_repository`:

```python
@pytest.fixture
def indicador_repository() -> FakeIndicadorTecnicoRepository:
    return FakeIndicadorTecnicoRepository()
```

E no `client` fixture, adicionar o parâmetro e o override:

```python
def client(
    usuario_repository: FakeUsuarioRepository,
    ativo_repository: FakeAtivoRepository,
    watchlist_repository: FakeWatchlistRepository,
    dados_mercado_service: FakeDadosMercadoService,
    cotacao_repository: FakeCotacaoRepository,
    indicador_repository: FakeIndicadorTecnicoRepository,
) -> TestClient:
    app.dependency_overrides[get_usuario_repository] = lambda: usuario_repository
    app.dependency_overrides[get_ativo_repository] = lambda: ativo_repository
    app.dependency_overrides[get_watchlist_repository] = lambda: watchlist_repository
    app.dependency_overrides[get_dados_mercado_service] = lambda: dados_mercado_service
    app.dependency_overrides[get_cotacao_repository] = lambda: cotacao_repository
    app.dependency_overrides[get_indicador_tecnico_repository] = lambda: indicador_repository
```

(mantendo o `with TestClient(app) as test_client: ...` que já vem depois)

- [ ] **Step 4: Escrever o teste do endpoint (RED)**

Arquivo `tests/unit/api/test_indicador_controller.py`:

```python
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from app.domain.entities.ativo import Ativo
from app.domain.entities.cotacao import Cotacao
from app.domain.enums.tipo_ativo import TipoAtivo

_PETR4 = Ativo(
    id=uuid4(),
    ticker="PETR4",
    nome="Petrobras PN",
    tipo=TipoAtivo.ACAO,
    setor="Petroleo e Gas",
    moeda="BRL",
    fonte_dados="brapi",
)


def _cotacoes_diarias(dias: int) -> list[Cotacao]:
    base = datetime(2024, 1, 1, tzinfo=UTC)
    return [
        Cotacao(
            id=uuid4(),
            ativo_id=_PETR4.id,
            data_hora=base + timedelta(days=i),
            abertura=Decimal("10"),
            maxima=Decimal("10"),
            minima=Decimal("10"),
            fechamento=Decimal("10"),
            volume=Decimal("1000000"),
        )
        for i in range(dias)
    ]


def test_indicadores_sem_token_retorna_401(client, ativo_repository):
    ativo_repository.salvar(_PETR4)

    resposta = client.get(f"/api/v1/ativos/{_PETR4.id}/indicadores")

    assert resposta.status_code == 401


def test_indicadores_calcula_e_retorna_para_o_ativo(
    client, auth_headers, ativo_repository, cotacao_repository
):
    ativo_repository.salvar(_PETR4)
    cotacao_repository.salvar_muitas(_cotacoes_diarias(60))

    resposta = client.get(f"/api/v1/ativos/{_PETR4.id}/indicadores", headers=auth_headers)

    assert resposta.status_code == 200
    corpo = resposta.json()
    tipos = {item["tipo"] for item in corpo}
    assert "SMA" in tipos
    assert "RSI" in tipos


def test_indicadores_de_ativo_inexistente_retorna_404(client, auth_headers):
    resposta = client.get(f"/api/v1/ativos/{uuid4()}/indicadores", headers=auth_headers)

    assert resposta.status_code == 404
```

- [ ] **Step 5: Rodar e confirmar RED**

```bash
.venv/bin/python -m pytest tests/unit/api/test_indicador_controller.py -q
```

Esperado: falha com `404` em vez de `200`/`401` (rota `/indicadores` ainda não existe) — confirmar que a falha é por rota ausente, não por erro de digitação no teste.

- [ ] **Step 6: Adicionar o endpoint em `src/app/api/v1/controllers/ativos.py`**

No topo do arquivo, ajustar os imports:

```python
from app.api.deps import (
    get_ativo_service,
    get_dados_mercado_service,
    get_indicador_service,
    get_usuario_atual,
)
from app.api.v1.schemas.ativo import AtivoEncontradoResponse
from app.api.v1.schemas.cotacao import CotacaoAtualResponse, PontoHistoricoResponse
from app.api.v1.schemas.indicador import IndicadorTecnicoResponse
from app.domain.entities.usuario import Usuario
from app.domain.enums.periodo_historico import PeriodoHistorico
from app.integrations.brapi.client import BrapiIndisponivelError, TickerNaoEncontradoError
from app.services.ativo_service import AtivoService
from app.services.dados_mercado_service import DadosMercadoService
from app.services.exceptions import AtivoNaoEncontradoError
from app.services.indicador_service import IndicadorService
```

No final do arquivo, adicionar o novo endpoint:

```python
@router.get("/{ativo_id}/indicadores", response_model=list[IndicadorTecnicoResponse])
def indicadores(
    ativo_id: UUID,
    usuario: Usuario = Depends(get_usuario_atual),
    service: IndicadorService = Depends(get_indicador_service),
) -> list[IndicadorTecnicoResponse]:
    try:
        calculados = service.calcular_todos(ativo_id)
    except AtivoNaoEncontradoError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ativo nao encontrado") from exc

    return [IndicadorTecnicoResponse.de(indicador) for indicador in calculados]
```

- [ ] **Step 7: Rodar e confirmar GREEN**

```bash
.venv/bin/python -m pytest tests/unit/api/test_indicador_controller.py -q
```

Esperado: `3 passed`.

- [ ] **Step 8: Rodar `ruff check` e a suíte completa**

```bash
.venv/bin/ruff check src/ tests/
.venv/bin/python -m pytest -q
```

Esperado: lint limpo, todos os testes passando (unitários + integração, com Postgres do docker-compose no ar).

- [ ] **Step 9: Testar manualmente contra a API real (opcional mas recomendado)**

```bash
docker compose up -d postgres redis
DATABASE_URL="postgresql://insightflow:insightflow@localhost:5432/insightflow" .venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --app-dir src --reload &
```

Cadastrar um usuário, pegar o token, buscar um ativo (`PETR4` funciona sem `BRAPI_API_KEY` no ambiente sandbox), chamar `/historico?periodo=1M` algumas vezes pra popular `cotacoes`, depois `GET /ativos/{id}/indicadores` e conferir a resposta no Swagger (`/docs`). Derrubar o `uvicorn` (`kill %1`) ao terminar.

- [ ] **Step 10: Commit**

```bash
git add src/app/api/v1/schemas/indicador.py src/app/api/v1/controllers/ativos.py src/app/api/deps.py tests/unit/api/conftest.py tests/unit/api/test_indicador_controller.py
git commit -m "feat(indicadores): adiciona endpoint GET /ativos/{id}/indicadores"
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

Nenhuma mudança em `cotacoes`, `Scheduler`, `SinalService` ou fora do escopo descrito na spec.
