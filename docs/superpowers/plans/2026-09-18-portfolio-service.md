# PortfolioService Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the PortfolioService vertical (RF-10/11/12): CRUD of fictitious operations, current positions, portfolio profitability, benchmark comparison (CDI/Ibovespa), and portfolio distribution by class/sector/currency.

**Architecture:** New `Operacao` persistence (repository + migration) feeds a pure `replay_operacoes` function that reconstructs weighted-average position state per asset. `PortfolioService` orchestrates that replay against `AtivoRepository`, `DadosMercadoService` (quotes), `CambioService` (BRL conversion) and `BcbClient` (CDI). A new REST controller exposes it, wired through `api/deps.py` the same way `AlertaService` is.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, Pydantic, Alembic, pytest, httpx (`MockTransport` for HTTP-layer unit tests).

**Spec:** `docs/superpowers/specs/2026-09-18-portfolio-service-design.md`

## Global Constraints

- Zero comments in source code, including short "why" comments (project-wide convention, see `CLAUDE.md`).
- Domain naming in Portuguese: entities, methods, variables, test names (`registrar_operacao`, `QuantidadeInsuficienteError`, `test_venda_parcial_nao_altera_preco_medio`).
- Every repository ships three parts together: ABC in `repositories/interfaces/`, SQLAlchemy impl in `repositories/sqlalchemy/`, `Fake*Repository` in `tests/fixtures/`.
- Commit messages: Conventional Commits in Portuguese with scope, e.g. `feat(portfolio): adiciona PortfolioService (CRUD)`.
- `rentabilidade()` and `comparativo_benchmark()` take no `periodo` parameter — always "since the first operation" (spec deviation from the doc, documented there).
- Weighted-average cost method only (no FIFO) — see spec's `replay_operacoes` pseudocode.
- **Commit discipline for whoever executes this plan:** this user normally commits personally in interactive sessions. Execution here happens in an isolated worktree on a throwaway feature branch (nothing shared, nothing pushed), and the SDD ledger's recovery mechanism depends on a real commit per task — so implementers DO run `git commit` at each task's "Commit" step in this worktree. The "ask before commit" preference re-applies at the merge/push/PR boundary, handled later as its own explicit step (see `finishing-a-development-branch`).
- Run tests with the project's venv binaries, never bare `pytest`: `.venv/bin/pytest tests/unit -v` for unit (no DB needed), `.venv/bin/pytest tests/ -m integration -v` for integration (needs `docker compose up -d postgres redis`).

---

## Task 1: Operacao persistence — model, migration, repository

**Files:**
- Create: `src/app/db/models/operacao.py`
- Create: `alembic/versions/a1c4f7e9d203_cria_tabela_operacoes.py`
- Create: `src/app/repositories/interfaces/operacao_repository.py`
- Create: `src/app/repositories/sqlalchemy/operacao_repository.py`
- Create: `tests/fixtures/fake_operacao_repository.py`
- Modify: `tests/integration/conftest.py` (register `OperacaoModel` so `Base.metadata.create_all` creates the table)
- Test: `tests/integration/repositories/test_operacao_repository.py`

**Interfaces:**
- Consumes: `app.domain.entities.operacao.Operacao` (already exists), `app.domain.enums.tipo_operacao.TipoOperacao` (already exists).
- Produces: `OperacaoRepository` ABC with `salvar(operacao)`, `buscar_por_id(operacao_id) -> Operacao | None`, `listar_por_usuario(usuario_id) -> list[Operacao]`, `remover(operacao)`. `SqlAlchemyOperacaoRepository` and `FakeOperacaoRepository` implement it. Later tasks depend on these four method names exactly.

- [ ] **Step 1: Write the failing integration test**

```python
# tests/integration/repositories/test_operacao_repository.py
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.entities.ativo import Ativo
from app.domain.entities.operacao import Operacao
from app.domain.entities.usuario import Usuario
from app.domain.enums.tipo_ativo import TipoAtivo
from app.domain.enums.tipo_operacao import TipoOperacao
from app.repositories.sqlalchemy.ativo_repository import SqlAlchemyAtivoRepository
from app.repositories.sqlalchemy.operacao_repository import SqlAlchemyOperacaoRepository
from app.repositories.sqlalchemy.usuario_repository import SqlAlchemyUsuarioRepository

pytestmark = pytest.mark.integration


def _novo_usuario(session) -> Usuario:
    usuario = Usuario.criar(
        id=uuid4(),
        nome="Ana",
        email=f"ana-{uuid4()}@example.com",
        senha="segredo123",
        criado_em=datetime(2026, 9, 8, 12, 0, 0, tzinfo=UTC),
    )
    SqlAlchemyUsuarioRepository(session).salvar(usuario)
    return usuario


def _novo_ativo(session, ticker: str = "PETR4") -> Ativo:
    ativo = Ativo(
        id=uuid4(),
        ticker=ticker,
        nome="Petrobras PN",
        tipo=TipoAtivo.ACAO,
        setor="Petroleo e Gas",
        moeda="BRL",
        fonte_dados="manual",
    )
    SqlAlchemyAtivoRepository(session).salvar(ativo)
    return ativo


def _nova_operacao(usuario_id, ativo_id, tipo=TipoOperacao.COMPRA) -> Operacao:
    return Operacao(
        id=uuid4(),
        usuario_id=usuario_id,
        ativo_id=ativo_id,
        tipo=tipo,
        quantidade=Decimal("10"),
        preco_unitario=Decimal("30.00"),
        data=date(2026, 9, 1),
        criado_em=datetime(2026, 9, 1, 10, 0, 0, tzinfo=UTC),
    )


def test_salvar_e_buscar_por_id_retorna_a_operacao_criada(session):
    usuario = _novo_usuario(session)
    ativo = _novo_ativo(session)
    repo = SqlAlchemyOperacaoRepository(session)
    operacao = _nova_operacao(usuario.id, ativo.id)

    repo.salvar(operacao)
    encontrada = repo.buscar_por_id(operacao.id)

    assert encontrada is not None
    assert encontrada.usuario_id == usuario.id
    assert encontrada.ativo_id == ativo.id
    assert encontrada.tipo == TipoOperacao.COMPRA
    assert encontrada.quantidade == Decimal("10")
    assert encontrada.preco_unitario == Decimal("30.00")
    assert encontrada.data == date(2026, 9, 1)


def test_buscar_por_id_inexistente_retorna_none(session):
    repo = SqlAlchemyOperacaoRepository(session)

    assert repo.buscar_por_id(uuid4()) is None


def test_listar_por_usuario_retorna_apenas_as_do_usuario(session):
    usuario = _novo_usuario(session)
    outro_usuario = _novo_usuario(session)
    ativo = _novo_ativo(session)
    repo = SqlAlchemyOperacaoRepository(session)
    repo.salvar(_nova_operacao(usuario.id, ativo.id))
    repo.salvar(_nova_operacao(outro_usuario.id, ativo.id))

    operacoes = repo.listar_por_usuario(usuario.id)

    assert len(operacoes) == 1
    assert operacoes[0].usuario_id == usuario.id


def test_remover_apaga_a_operacao(session):
    usuario = _novo_usuario(session)
    ativo = _novo_ativo(session)
    repo = SqlAlchemyOperacaoRepository(session)
    operacao = _nova_operacao(usuario.id, ativo.id)
    repo.salvar(operacao)

    repo.remover(operacao)

    assert repo.buscar_por_id(operacao.id) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/integration/repositories/test_operacao_repository.py -v -m integration`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.repositories.sqlalchemy.operacao_repository'` (requires `docker compose up -d postgres redis` running first).

- [ ] **Step 3: Write the entity-adjacent pieces (enum already exists — just the ABC, model, impl, fake, migration)**

```python
# src/app/repositories/interfaces/operacao_repository.py
from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.operacao import Operacao


class OperacaoRepository(ABC):
    @abstractmethod
    def salvar(self, operacao: Operacao) -> None: ...

    @abstractmethod
    def buscar_por_id(self, operacao_id: UUID) -> Operacao | None: ...

    @abstractmethod
    def listar_por_usuario(self, usuario_id: UUID) -> list[Operacao]: ...

    @abstractmethod
    def remover(self, operacao: Operacao) -> None: ...
```

```python
# src/app/db/models/operacao.py
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OperacaoModel(Base):
    __tablename__ = "operacoes"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    usuario_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("usuarios.id"), nullable=False)
    ativo_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("ativos.id"), nullable=False)
    tipo: Mapped[str] = mapped_column(String(10), nullable=False)
    quantidade: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    preco_unitario: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    data: Mapped[date] = mapped_column(Date, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

```python
# alembic/versions/a1c4f7e9d203_cria_tabela_operacoes.py
"""cria tabela operacoes

Revision ID: a1c4f7e9d203
Revises: 12b09b3cdf77
Create Date: 2026-09-18 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a1c4f7e9d203"
down_revision: str | Sequence[str] | None = "12b09b3cdf77"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operacoes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("ativo_id", sa.Uuid(), nullable=False),
        sa.Column("tipo", sa.String(length=10), nullable=False),
        sa.Column("quantidade", sa.Numeric(18, 6), nullable=False),
        sa.Column("preco_unitario", sa.Numeric(18, 6), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
        sa.ForeignKeyConstraint(["ativo_id"], ["ativos.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("operacoes")
```

```python
# src/app/repositories/sqlalchemy/operacao_repository.py
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.operacao import OperacaoModel
from app.domain.entities.operacao import Operacao
from app.domain.enums.tipo_operacao import TipoOperacao
from app.repositories.interfaces.operacao_repository import OperacaoRepository


class SqlAlchemyOperacaoRepository(OperacaoRepository):
    def __init__(self, session: Session):
        self._session = session

    def salvar(self, operacao: Operacao) -> None:
        modelo = self._session.get(OperacaoModel, operacao.id)
        if modelo is None:
            modelo = OperacaoModel(id=operacao.id)
            self._session.add(modelo)

        modelo.usuario_id = operacao.usuario_id
        modelo.ativo_id = operacao.ativo_id
        modelo.tipo = operacao.tipo
        modelo.quantidade = operacao.quantidade
        modelo.preco_unitario = operacao.preco_unitario
        modelo.data = operacao.data
        modelo.criado_em = operacao.criado_em
        self._session.commit()

    def buscar_por_id(self, operacao_id: UUID) -> Operacao | None:
        modelo = self._session.get(OperacaoModel, operacao_id)
        return self._para_entidade(modelo) if modelo is not None else None

    def listar_por_usuario(self, usuario_id: UUID) -> list[Operacao]:
        modelos = self._session.scalars(
            select(OperacaoModel).where(OperacaoModel.usuario_id == usuario_id)
        )
        return [self._para_entidade(modelo) for modelo in modelos]

    def remover(self, operacao: Operacao) -> None:
        modelo = self._session.get(OperacaoModel, operacao.id)
        if modelo is not None:
            self._session.delete(modelo)
            self._session.commit()

    @staticmethod
    def _para_entidade(modelo: OperacaoModel) -> Operacao:
        return Operacao(
            id=modelo.id,
            usuario_id=modelo.usuario_id,
            ativo_id=modelo.ativo_id,
            tipo=TipoOperacao(modelo.tipo),
            quantidade=modelo.quantidade,
            preco_unitario=modelo.preco_unitario,
            data=modelo.data,
            criado_em=modelo.criado_em,
        )
```

```python
# tests/fixtures/fake_operacao_repository.py
from __future__ import annotations

from uuid import UUID

from app.domain.entities.operacao import Operacao
from app.repositories.interfaces.operacao_repository import OperacaoRepository


class FakeOperacaoRepository(OperacaoRepository):
    def __init__(self) -> None:
        self._operacoes: dict[UUID, Operacao] = {}

    def salvar(self, operacao: Operacao) -> None:
        self._operacoes[operacao.id] = operacao

    def buscar_por_id(self, operacao_id: UUID) -> Operacao | None:
        return self._operacoes.get(operacao_id)

    def listar_por_usuario(self, usuario_id: UUID) -> list[Operacao]:
        return [op for op in self._operacoes.values() if op.usuario_id == usuario_id]

    def remover(self, operacao: Operacao) -> None:
        self._operacoes.pop(operacao.id, None)
```

Modify `tests/integration/conftest.py` — add the import alongside the other model imports so `Base.metadata.create_all(engine)` creates the `operacoes` table:

```python
from app.db.models.operacao import OperacaoModel
```

(Insert it alphabetically among the existing `from app.db.models....` import lines.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/integration/repositories/test_operacao_repository.py -v -m integration`
Expected: PASS (4 tests). If it fails with a schema error, run `.venv/bin/alembic upgrade head` against the test database first — the integration `engine` fixture uses `Base.metadata.create_all`, not Alembic, so the migration itself is only exercised by `alembic upgrade head` in a real environment, not by this test; run `.venv/bin/alembic check` to confirm the new revision doesn't drift from the models.

- [ ] **Step 5: Commit**

```bash
git add src/app/db/models/operacao.py alembic/versions/a1c4f7e9d203_cria_tabela_operacoes.py \
  src/app/repositories/interfaces/operacao_repository.py \
  src/app/repositories/sqlalchemy/operacao_repository.py \
  tests/fixtures/fake_operacao_repository.py \
  tests/integration/conftest.py \
  tests/integration/repositories/test_operacao_repository.py
```
Draft message (stage only, do not commit unless the user asks):
```
feat(portfolio): adiciona persistencia de Operacao (repository, model, migration)
```

---

## Task 2: Replay de operações — cálculo de posição por preço médio ponderado

**Files:**
- Create: `src/app/services/portfolio_service.py` (starts with just `EstadoPosicao` + `replay_operacoes`)
- Modify: `src/app/services/exceptions.py` (add `QuantidadeInsuficienteError`)
- Test: `tests/unit/services/test_portfolio_service.py`

**Interfaces:**
- Consumes: `Operacao`, `TipoOperacao` (existing).
- Produces: `EstadoPosicao` dataclass (`quantidade: Decimal`, `preco_medio: Decimal`, `lucro_realizado: Decimal`) and `replay_operacoes(operacoes: list[Operacao]) -> EstadoPosicao`. Task 3 onward import both by these exact names from `app.services.portfolio_service`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/services/test_portfolio_service.py
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.entities.operacao import Operacao
from app.domain.enums.tipo_operacao import TipoOperacao
from app.services.exceptions import QuantidadeInsuficienteError
from app.services.portfolio_service import replay_operacoes


def _operacao(tipo, quantidade, preco, dia, criado_em_hora=10) -> Operacao:
    return Operacao(
        id=uuid4(),
        usuario_id=uuid4(),
        ativo_id=uuid4(),
        tipo=tipo,
        quantidade=Decimal(quantidade),
        preco_unitario=Decimal(preco),
        data=date(2026, 9, dia),
        criado_em=datetime(2026, 9, dia, criado_em_hora, 0, 0, tzinfo=UTC),
    )


def test_compra_unica_define_quantidade_e_preco_medio():
    estado = replay_operacoes([_operacao(TipoOperacao.COMPRA, "10", "30.00", 1)])

    assert estado.quantidade == Decimal("10")
    assert estado.preco_medio == Decimal("30.00")
    assert estado.lucro_realizado == Decimal("0")


def test_compras_multiplas_calculam_media_ponderada():
    operacoes = [
        _operacao(TipoOperacao.COMPRA, "10", "30.00", 1),
        _operacao(TipoOperacao.COMPRA, "10", "40.00", 2),
    ]

    estado = replay_operacoes(operacoes)

    assert estado.quantidade == Decimal("20")
    assert estado.preco_medio == Decimal("35.00")


def test_venda_parcial_nao_altera_preco_medio():
    operacoes = [
        _operacao(TipoOperacao.COMPRA, "10", "30.00", 1),
        _operacao(TipoOperacao.VENDA, "4", "50.00", 2),
    ]

    estado = replay_operacoes(operacoes)

    assert estado.quantidade == Decimal("6")
    assert estado.preco_medio == Decimal("30.00")
    assert estado.lucro_realizado == Decimal("80.00")


def test_venda_total_zera_quantidade_e_reseta_preco_medio():
    operacoes = [
        _operacao(TipoOperacao.COMPRA, "10", "30.00", 1),
        _operacao(TipoOperacao.VENDA, "10", "50.00", 2),
    ]

    estado = replay_operacoes(operacoes)

    assert estado.quantidade == Decimal("0")
    assert estado.preco_medio == Decimal("0")
    assert estado.lucro_realizado == Decimal("200.00")


def test_compra_apos_zerar_nao_herda_media_antiga():
    operacoes = [
        _operacao(TipoOperacao.COMPRA, "10", "30.00", 1),
        _operacao(TipoOperacao.VENDA, "10", "50.00", 2),
        _operacao(TipoOperacao.COMPRA, "5", "80.00", 3),
    ]

    estado = replay_operacoes(operacoes)

    assert estado.quantidade == Decimal("5")
    assert estado.preco_medio == Decimal("80.00")


def test_venda_lucrativa_parcial_nao_estoura_lucro_realizado_mesmo_fora_de_ordem():
    operacoes = [
        _operacao(TipoOperacao.VENDA, "4", "50.00", 2),
        _operacao(TipoOperacao.COMPRA, "10", "30.00", 1),
    ]

    estado = replay_operacoes(operacoes)

    assert estado.quantidade == Decimal("6")
    assert estado.lucro_realizado == Decimal("80.00")


def test_operacoes_no_mesmo_dia_usam_criado_em_como_desempate():
    operacoes = [
        _operacao(TipoOperacao.VENDA, "10", "50.00", 1, criado_em_hora=15),
        _operacao(TipoOperacao.COMPRA, "10", "30.00", 1, criado_em_hora=9),
    ]

    estado = replay_operacoes(operacoes)

    assert estado.quantidade == Decimal("0")
    assert estado.lucro_realizado == Decimal("200.00")


def test_venda_maior_que_posicao_levanta_quantidade_insuficiente():
    operacoes = [
        _operacao(TipoOperacao.COMPRA, "5", "30.00", 1),
        _operacao(TipoOperacao.VENDA, "10", "50.00", 2),
    ]

    with pytest.raises(QuantidadeInsuficienteError):
        replay_operacoes(operacoes)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/services/test_portfolio_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.portfolio_service'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/app/services/exceptions.py — append at the end of the file
class QuantidadeInsuficienteError(Exception):
    pass
```

```python
# src/app/services/portfolio_service.py
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.entities.operacao import Operacao
from app.domain.enums.tipo_operacao import TipoOperacao
from app.services.exceptions import QuantidadeInsuficienteError


@dataclass
class EstadoPosicao:
    quantidade: Decimal = Decimal(0)
    preco_medio: Decimal = Decimal(0)
    lucro_realizado: Decimal = Decimal(0)


def replay_operacoes(operacoes: list[Operacao]) -> EstadoPosicao:
    estado = EstadoPosicao()
    for op in sorted(operacoes, key=lambda o: (o.data, o.criado_em)):
        if op.tipo == TipoOperacao.COMPRA:
            custo_total = estado.quantidade * estado.preco_medio + op.valor_total()
            estado.quantidade += op.quantidade
            estado.preco_medio = custo_total / estado.quantidade
        else:
            if op.quantidade > estado.quantidade:
                raise QuantidadeInsuficienteError(op.ativo_id)
            estado.lucro_realizado += (op.preco_unitario - estado.preco_medio) * op.quantidade
            estado.quantidade -= op.quantidade
            if estado.quantidade == 0:
                estado.preco_medio = Decimal(0)
    return estado
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/services/test_portfolio_service.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add src/app/services/portfolio_service.py src/app/services/exceptions.py \
  tests/unit/services/test_portfolio_service.py
```
Draft message:
```
feat(portfolio): adiciona replay de operacoes para calculo de posicao
```

---

## Task 3: CRUD de operações no PortfolioService

**Files:**
- Modify: `src/app/services/portfolio_service.py` (add `PortfolioService` class)
- Modify: `src/app/services/exceptions.py` (add `OperacaoInvalidaError`, `OperacaoNaoEncontradaError`)
- Test: `tests/unit/services/test_portfolio_service.py` (append)

**Interfaces:**
- Consumes: `OperacaoRepository`, `AtivoRepository` (existing), `replay_operacoes`/`EstadoPosicao` from Task 2.
- Produces: `PortfolioService.__init__(operacao_repository, ativo_repository, dados_mercado_service, cambio_service, bcb_client)`, `registrar_operacao(usuario_id, ativo_id, tipo, quantidade, preco_unitario, data) -> Operacao`, `listar_operacoes(usuario_id) -> list[Operacao]`, `remover_operacao(usuario_id, operacao_id) -> None`. `dados_mercado_service`/`cambio_service`/`bcb_client` constructor params are accepted now but unused until Tasks 4/5/8 — later tasks must not change this constructor signature.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/services/test_portfolio_service.py — append
from app.domain.entities.ativo import Ativo
from app.domain.enums.tipo_ativo import TipoAtivo
from app.services.exceptions import (
    AtivoNaoEncontradoError,
    OperacaoInvalidaError,
    OperacaoNaoEncontradaError,
)
from app.services.portfolio_service import PortfolioService
from tests.fixtures.fake_ativo_repository import FakeAtivoRepository
from tests.fixtures.fake_cambio_service import FakeCambioService
from tests.fixtures.fake_dados_mercado_service import FakeDadosMercadoService
from tests.fixtures.fake_operacao_repository import FakeOperacaoRepository

_PETR4 = Ativo(
    id=uuid4(),
    ticker="PETR4",
    nome="Petrobras PN",
    tipo=TipoAtivo.ACAO,
    setor="Petroleo e Gas",
    moeda="BRL",
    fonte_dados="manual",
)


def _service(ativos=None):
    ativo_repository = FakeAtivoRepository()
    for ativo in ativos or [_PETR4]:
        ativo_repository.salvar(ativo)
    return PortfolioService(
        FakeOperacaoRepository(),
        ativo_repository,
        FakeDadosMercadoService(),
        FakeCambioService(),
        bcb_client=None,
    )


def test_registrar_operacao_persiste_compra():
    service = _service()
    usuario_id = uuid4()

    operacao = service.registrar_operacao(
        usuario_id=usuario_id,
        ativo_id=_PETR4.id,
        tipo=TipoOperacao.COMPRA,
        quantidade=Decimal("10"),
        preco_unitario=Decimal("30.00"),
        data=date(2026, 9, 1),
    )

    assert operacao.usuario_id == usuario_id
    assert service.listar_operacoes(usuario_id) == [operacao]


def test_registrar_operacao_quantidade_invalida_lanca_erro():
    service = _service()

    with pytest.raises(OperacaoInvalidaError):
        service.registrar_operacao(
            usuario_id=uuid4(),
            ativo_id=_PETR4.id,
            tipo=TipoOperacao.COMPRA,
            quantidade=Decimal("0"),
            preco_unitario=Decimal("30.00"),
            data=date(2026, 9, 1),
        )


def test_registrar_operacao_preco_invalido_lanca_erro():
    service = _service()

    with pytest.raises(OperacaoInvalidaError):
        service.registrar_operacao(
            usuario_id=uuid4(),
            ativo_id=_PETR4.id,
            tipo=TipoOperacao.COMPRA,
            quantidade=Decimal("10"),
            preco_unitario=Decimal("-1"),
            data=date(2026, 9, 1),
        )


def test_registrar_operacao_data_futura_lanca_erro():
    service = _service()

    with pytest.raises(OperacaoInvalidaError):
        service.registrar_operacao(
            usuario_id=uuid4(),
            ativo_id=_PETR4.id,
            tipo=TipoOperacao.COMPRA,
            quantidade=Decimal("10"),
            preco_unitario=Decimal("30.00"),
            data=date(2100, 1, 1),
        )


def test_registrar_operacao_ativo_inexistente_lanca_erro():
    service = _service(ativos=[])

    with pytest.raises(AtivoNaoEncontradoError):
        service.registrar_operacao(
            usuario_id=uuid4(),
            ativo_id=_PETR4.id,
            tipo=TipoOperacao.COMPRA,
            quantidade=Decimal("10"),
            preco_unitario=Decimal("30.00"),
            data=date(2026, 9, 1),
        )


def test_registrar_venda_sem_posicao_lanca_quantidade_insuficiente():
    service = _service()

    with pytest.raises(QuantidadeInsuficienteError):
        service.registrar_operacao(
            usuario_id=uuid4(),
            ativo_id=_PETR4.id,
            tipo=TipoOperacao.VENDA,
            quantidade=Decimal("10"),
            preco_unitario=Decimal("30.00"),
            data=date(2026, 9, 1),
        )


def test_listar_operacoes_retorna_apenas_as_do_usuario():
    service = _service()
    usuario_id = uuid4()
    service.registrar_operacao(
        usuario_id=usuario_id,
        ativo_id=_PETR4.id,
        tipo=TipoOperacao.COMPRA,
        quantidade=Decimal("10"),
        preco_unitario=Decimal("30.00"),
        data=date(2026, 9, 1),
    )
    service.registrar_operacao(
        usuario_id=uuid4(),
        ativo_id=_PETR4.id,
        tipo=TipoOperacao.COMPRA,
        quantidade=Decimal("5"),
        preco_unitario=Decimal("30.00"),
        data=date(2026, 9, 1),
    )

    assert len(service.listar_operacoes(usuario_id)) == 1


def test_remover_operacao_remove_do_dono():
    service = _service()
    usuario_id = uuid4()
    operacao = service.registrar_operacao(
        usuario_id=usuario_id,
        ativo_id=_PETR4.id,
        tipo=TipoOperacao.COMPRA,
        quantidade=Decimal("10"),
        preco_unitario=Decimal("30.00"),
        data=date(2026, 9, 1),
    )

    service.remover_operacao(usuario_id, operacao.id)

    assert service.listar_operacoes(usuario_id) == []


def test_remover_operacao_de_outro_usuario_lanca_erro():
    service = _service()
    dono = uuid4()
    outro = uuid4()
    operacao = service.registrar_operacao(
        usuario_id=dono,
        ativo_id=_PETR4.id,
        tipo=TipoOperacao.COMPRA,
        quantidade=Decimal("10"),
        preco_unitario=Decimal("30.00"),
        data=date(2026, 9, 1),
    )

    with pytest.raises(OperacaoNaoEncontradaError):
        service.remover_operacao(outro, operacao.id)


def test_remover_operacao_inexistente_lanca_erro():
    service = _service()

    with pytest.raises(OperacaoNaoEncontradaError):
        service.remover_operacao(uuid4(), uuid4())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/services/test_portfolio_service.py -v`
Expected: FAIL — `ImportError: cannot import name 'PortfolioService'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/app/services/exceptions.py — append
class OperacaoInvalidaError(Exception):
    pass


class OperacaoNaoEncontradaError(Exception):
    pass
```

```python
# src/app/services/portfolio_service.py — append below replay_operacoes
import logging
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from app.integrations.bcb.client import BcbClient
from app.repositories.interfaces.ativo_repository import AtivoRepository
from app.repositories.interfaces.operacao_repository import OperacaoRepository
from app.services.cambio_service import CambioService
from app.services.dados_mercado_service import DadosMercadoService
from app.services.exceptions import (
    AtivoNaoEncontradoError,
    OperacaoInvalidaError,
    OperacaoNaoEncontradaError,
)

logger = logging.getLogger(__name__)


class PortfolioService:
    def __init__(
        self,
        operacao_repository: OperacaoRepository,
        ativo_repository: AtivoRepository,
        dados_mercado_service: DadosMercadoService,
        cambio_service: CambioService,
        bcb_client: BcbClient,
    ):
        self._operacao_repository = operacao_repository
        self._ativo_repository = ativo_repository
        self._dados_mercado_service = dados_mercado_service
        self._cambio_service = cambio_service
        self._bcb_client = bcb_client

    def registrar_operacao(
        self,
        usuario_id: UUID,
        ativo_id: UUID,
        tipo: TipoOperacao,
        quantidade: Decimal,
        preco_unitario: Decimal,
        data: date,
    ) -> Operacao:
        if quantidade <= 0:
            raise OperacaoInvalidaError("quantidade deve ser maior que zero")
        if preco_unitario <= 0:
            raise OperacaoInvalidaError("preco_unitario deve ser maior que zero")
        if data > date.today():
            raise OperacaoInvalidaError("data nao pode ser futura")

        ativo = self._ativo_repository.buscar_por_id(ativo_id)
        if ativo is None:
            raise AtivoNaoEncontradoError(ativo_id)

        if tipo == TipoOperacao.VENDA:
            operacoes_existentes = [
                op
                for op in self._operacao_repository.listar_por_usuario(usuario_id)
                if op.ativo_id == ativo_id
            ]
            estado = replay_operacoes(operacoes_existentes)
            if quantidade > estado.quantidade:
                raise QuantidadeInsuficienteError(ativo_id)

        operacao = Operacao(
            id=uuid4(),
            usuario_id=usuario_id,
            ativo_id=ativo_id,
            tipo=tipo,
            quantidade=quantidade,
            preco_unitario=preco_unitario,
            data=data,
            criado_em=datetime.now(UTC),
        )
        self._operacao_repository.salvar(operacao)
        return operacao

    def listar_operacoes(self, usuario_id: UUID) -> list[Operacao]:
        return self._operacao_repository.listar_por_usuario(usuario_id)

    def remover_operacao(self, usuario_id: UUID, operacao_id: UUID) -> None:
        operacao = self._buscar_operacao(usuario_id, operacao_id)
        self._operacao_repository.remover(operacao)

    def _buscar_operacao(self, usuario_id: UUID, operacao_id: UUID) -> Operacao:
        operacao = self._operacao_repository.buscar_por_id(operacao_id)
        if operacao is None or operacao.usuario_id != usuario_id:
            raise OperacaoNaoEncontradaError(operacao_id)
        return operacao
```

Note: `Decimal`, `TipoOperacao`, `Operacao`, `QuantidadeInsuficienteError` are already imported at the top of `portfolio_service.py` from Task 2 — do not duplicate those imports, just add the new ones listed above alongside them.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/services/test_portfolio_service.py -v`
Expected: PASS (18 tests total: 8 from Task 2 + 10 from this task)

- [ ] **Step 5: Commit**

```bash
git add src/app/services/portfolio_service.py src/app/services/exceptions.py \
  tests/unit/services/test_portfolio_service.py
```
Draft message:
```
feat(portfolio): adiciona registrar/listar/remover operacao no PortfolioService
```

---

## Task 4: `posicoes()` — posição atual por ativo

**Files:**
- Create: `src/app/domain/value_objects/posicao.py`
- Modify: `src/app/services/portfolio_service.py`
- Test: `tests/unit/services/test_portfolio_service.py` (append)

**Interfaces:**
- Consumes: `EstadoPosicao`/`replay_operacoes` (Task 2), `DadosMercadoService.buscar_cotacao_atual(ticker) -> CotacaoAtual` (existing), `CambioService.converter(valor, de, para) -> Decimal` (existing).
- Produces: `Posicao` dataclass (`ativo_id`, `ticker`, `quantidade`, `preco_medio`, `cotacao_atual`, `valor_mercado`, `valor_mercado_brl`, `lucro_nao_realizado`, `lucro_realizado`); `PortfolioService.posicoes(usuario_id) -> list[Posicao]`; private helper `_replay_por_ativo(usuario_id) -> dict[UUID, EstadoPosicao]` that Tasks 5 and 6 reuse verbatim (do not reimplement it).

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/services/test_portfolio_service.py — append
from app.integrations.brapi.client import CotacaoAtual


def _cotacao(preco: str) -> CotacaoAtual:
    return CotacaoAtual(
        ticker="PETR4",
        preco=Decimal(preco),
        variacao=Decimal("0"),
        variacao_percentual=Decimal("0"),
        maxima_dia=Decimal(preco),
        minima_dia=Decimal(preco),
        volume=Decimal("0"),
    )


def _service_com_cotacao(preco: str, taxa_cambio: Decimal | None = None) -> PortfolioService:
    ativo_repository = FakeAtivoRepository()
    ativo_repository.salvar(_PETR4)
    return PortfolioService(
        FakeOperacaoRepository(),
        ativo_repository,
        FakeDadosMercadoService(cotacoes={"PETR4": _cotacao(preco)}),
        FakeCambioService(taxa=taxa_cambio if taxa_cambio is not None else Decimal("1")),
        bcb_client=None,
    )


def test_posicoes_calcula_valor_de_mercado_e_lucro_nao_realizado():
    service = _service_com_cotacao(preco="50.00")
    usuario_id = uuid4()
    service.registrar_operacao(
        usuario_id=usuario_id,
        ativo_id=_PETR4.id,
        tipo=TipoOperacao.COMPRA,
        quantidade=Decimal("10"),
        preco_unitario=Decimal("30.00"),
        data=date(2026, 9, 1),
    )

    posicoes = service.posicoes(usuario_id)

    assert len(posicoes) == 1
    posicao = posicoes[0]
    assert posicao.ativo_id == _PETR4.id
    assert posicao.quantidade == Decimal("10")
    assert posicao.preco_medio == Decimal("30.00")
    assert posicao.valor_mercado == Decimal("500.00")
    assert posicao.lucro_nao_realizado == Decimal("200.00")
    assert posicao.lucro_realizado == Decimal("0")


def test_posicoes_converte_valor_de_mercado_para_brl():
    service = _service_com_cotacao(preco="50.00", taxa_cambio=Decimal("5.00"))
    usuario_id = uuid4()
    service.registrar_operacao(
        usuario_id=usuario_id,
        ativo_id=_PETR4.id,
        tipo=TipoOperacao.COMPRA,
        quantidade=Decimal("10"),
        preco_unitario=Decimal("30.00"),
        data=date(2026, 9, 1),
    )

    posicao = service.posicoes(usuario_id)[0]

    assert posicao.valor_mercado == Decimal("500.00")
    assert posicao.valor_mercado_brl == Decimal("2500.00")


def test_posicoes_omite_ativos_totalmente_vendidos():
    service = _service_com_cotacao(preco="50.00")
    usuario_id = uuid4()
    service.registrar_operacao(
        usuario_id=usuario_id,
        ativo_id=_PETR4.id,
        tipo=TipoOperacao.COMPRA,
        quantidade=Decimal("10"),
        preco_unitario=Decimal("30.00"),
        data=date(2026, 9, 1),
    )
    service.registrar_operacao(
        usuario_id=usuario_id,
        ativo_id=_PETR4.id,
        tipo=TipoOperacao.VENDA,
        quantidade=Decimal("10"),
        preco_unitario=Decimal("50.00"),
        data=date(2026, 9, 2),
    )

    assert service.posicoes(usuario_id) == []


def test_posicoes_isola_por_usuario():
    service = _service_com_cotacao(preco="50.00")
    dono = uuid4()
    outro = uuid4()
    service.registrar_operacao(
        usuario_id=dono,
        ativo_id=_PETR4.id,
        tipo=TipoOperacao.COMPRA,
        quantidade=Decimal("10"),
        preco_unitario=Decimal("30.00"),
        data=date(2026, 9, 1),
    )

    assert service.posicoes(outro) == []
```

Note `FakeAtivoRepository` used in this test file's earlier `_service` and here is already imported at the top from Task 3.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/services/test_portfolio_service.py -v`
Expected: FAIL — `AttributeError: 'PortfolioService' object has no attribute 'posicoes'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/app/domain/value_objects/posicao.py
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID


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

```python
# src/app/services/portfolio_service.py — add import and methods to PortfolioService
from app.domain.value_objects.posicao import Posicao
from app.integrations.brapi.client import BrapiIndisponivelError, TickerNaoEncontradoError

# inside class PortfolioService, below remover_operacao:

    def posicoes(self, usuario_id: UUID) -> list[Posicao]:
        estados = self._replay_por_ativo(usuario_id)
        resultado: list[Posicao] = []
        for ativo_id, estado in estados.items():
            if estado.quantidade == 0:
                continue
            ativo = self._ativo_repository.buscar_por_id(ativo_id)
            try:
                cotacao = self._dados_mercado_service.buscar_cotacao_atual(ativo.ticker)
            except (BrapiIndisponivelError, TickerNaoEncontradoError):
                logger.warning(
                    "Cotacao indisponivel para %s; ativo omitido das posicoes.", ativo.ticker
                )
                continue

            valor_mercado = estado.quantidade * cotacao.preco
            valor_mercado_brl = self._cambio_service.converter(
                valor_mercado, de=ativo.moeda, para="BRL"
            )
            resultado.append(
                Posicao(
                    ativo_id=ativo_id,
                    ticker=ativo.ticker,
                    quantidade=estado.quantidade,
                    preco_medio=estado.preco_medio,
                    cotacao_atual=cotacao.preco,
                    valor_mercado=valor_mercado,
                    valor_mercado_brl=valor_mercado_brl,
                    lucro_nao_realizado=valor_mercado - (estado.quantidade * estado.preco_medio),
                    lucro_realizado=estado.lucro_realizado,
                )
            )
        return resultado

    def _replay_por_ativo(self, usuario_id: UUID) -> dict[UUID, EstadoPosicao]:
        operacoes_por_ativo: dict[UUID, list[Operacao]] = {}
        for operacao in self._operacao_repository.listar_por_usuario(usuario_id):
            operacoes_por_ativo.setdefault(operacao.ativo_id, []).append(operacao)
        return {
            ativo_id: replay_operacoes(operacoes)
            for ativo_id, operacoes in operacoes_por_ativo.items()
        }
```

`FakeCambioService.converter` already returns `valor` unchanged when `de == para` (base `CambioService.converter`), and `valor * taxa` otherwise — that's why `test_posicoes_calcula_valor_de_mercado_e_lucro_nao_realizado` uses `taxa=Decimal("1")` by default via `_service_com_cotacao`'s default argument.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/services/test_portfolio_service.py -v`
Expected: PASS (22 tests total)

- [ ] **Step 5: Commit**

```bash
git add src/app/domain/value_objects/posicao.py src/app/services/portfolio_service.py \
  tests/unit/services/test_portfolio_service.py
```
Draft message:
```
feat(portfolio): adiciona calculo de posicoes no PortfolioService
```

---

## Task 5: `rentabilidade()` — rentabilidade agregada da carteira

**Files:**
- Create: `src/app/domain/value_objects/rentabilidade.py`
- Modify: `src/app/services/portfolio_service.py`
- Test: `tests/unit/services/test_portfolio_service.py` (append)

**Interfaces:**
- Consumes: `_replay_por_ativo` (Task 4, produces `dict[UUID, EstadoPosicao]` including fully-sold assets).
- Produces: `Rentabilidade` dataclass (`custo_base_brl`, `valor_mercado_brl`, `lucro_nao_realizado_brl`, `lucro_realizado_brl`, `percentual`); `PortfolioService.rentabilidade(usuario_id) -> Rentabilidade`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/services/test_portfolio_service.py — append
def test_rentabilidade_calcula_percentual_sobre_custo_base():
    service = _service_com_cotacao(preco="50.00")
    usuario_id = uuid4()
    service.registrar_operacao(
        usuario_id=usuario_id,
        ativo_id=_PETR4.id,
        tipo=TipoOperacao.COMPRA,
        quantidade=Decimal("10"),
        preco_unitario=Decimal("30.00"),
        data=date(2026, 9, 1),
    )

    rentabilidade = service.rentabilidade(usuario_id)

    assert rentabilidade.custo_base_brl == Decimal("300.00")
    assert rentabilidade.valor_mercado_brl == Decimal("500.00")
    assert rentabilidade.lucro_nao_realizado_brl == Decimal("200.00")
    assert rentabilidade.percentual == Decimal("200.00") / Decimal("300.00")


def test_rentabilidade_nao_estoura_com_venda_parcial_lucrativa():
    service = _service_com_cotacao(preco="50.00")
    usuario_id = uuid4()
    service.registrar_operacao(
        usuario_id=usuario_id,
        ativo_id=_PETR4.id,
        tipo=TipoOperacao.COMPRA,
        quantidade=Decimal("10"),
        preco_unitario=Decimal("10.00"),
        data=date(2026, 9, 1),
    )
    service.registrar_operacao(
        usuario_id=usuario_id,
        ativo_id=_PETR4.id,
        tipo=TipoOperacao.VENDA,
        quantidade=Decimal("5"),
        preco_unitario=Decimal("30.00"),
        data=date(2026, 9, 2),
    )

    rentabilidade = service.rentabilidade(usuario_id)

    assert rentabilidade.lucro_realizado_brl == Decimal("100.00")
    assert rentabilidade.percentual >= Decimal("0")
    assert rentabilidade.percentual < Decimal("10")


def test_rentabilidade_inclui_lucro_realizado_de_ativo_totalmente_vendido():
    service = _service_com_cotacao(preco="50.00")
    usuario_id = uuid4()
    service.registrar_operacao(
        usuario_id=usuario_id,
        ativo_id=_PETR4.id,
        tipo=TipoOperacao.COMPRA,
        quantidade=Decimal("10"),
        preco_unitario=Decimal("30.00"),
        data=date(2026, 9, 1),
    )
    service.registrar_operacao(
        usuario_id=usuario_id,
        ativo_id=_PETR4.id,
        tipo=TipoOperacao.VENDA,
        quantidade=Decimal("10"),
        preco_unitario=Decimal("50.00"),
        data=date(2026, 9, 2),
    )

    rentabilidade = service.rentabilidade(usuario_id)

    assert rentabilidade.lucro_realizado_brl == Decimal("200.00")
    assert rentabilidade.custo_base_brl == Decimal("0")
    assert rentabilidade.percentual == Decimal("0")


def test_rentabilidade_sem_operacoes_retorna_zeros():
    service = _service_com_cotacao(preco="50.00")

    rentabilidade = service.rentabilidade(uuid4())

    assert rentabilidade.custo_base_brl == Decimal("0")
    assert rentabilidade.valor_mercado_brl == Decimal("0")
    assert rentabilidade.percentual == Decimal("0")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/services/test_portfolio_service.py -v`
Expected: FAIL — `AttributeError: 'PortfolioService' object has no attribute 'rentabilidade'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/app/domain/value_objects/rentabilidade.py
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class Rentabilidade:
    custo_base_brl: Decimal
    valor_mercado_brl: Decimal
    lucro_nao_realizado_brl: Decimal
    lucro_realizado_brl: Decimal
    percentual: Decimal
```

```python
# src/app/services/portfolio_service.py — add import and method
from app.domain.value_objects.rentabilidade import Rentabilidade

# inside class PortfolioService, below posicoes()/_replay_por_ativo:

    def rentabilidade(self, usuario_id: UUID) -> Rentabilidade:
        estados = self._replay_por_ativo(usuario_id)
        custo_base_brl = Decimal(0)
        valor_mercado_brl = Decimal(0)
        lucro_realizado_brl = Decimal(0)

        for ativo_id, estado in estados.items():
            ativo = self._ativo_repository.buscar_por_id(ativo_id)
            lucro_realizado_brl += self._cambio_service.converter(
                estado.lucro_realizado, de=ativo.moeda, para="BRL"
            )
            if estado.quantidade == 0:
                continue

            custo_base = estado.quantidade * estado.preco_medio
            custo_base_brl += self._cambio_service.converter(custo_base, de=ativo.moeda, para="BRL")
            try:
                cotacao = self._dados_mercado_service.buscar_cotacao_atual(ativo.ticker)
            except (BrapiIndisponivelError, TickerNaoEncontradoError):
                logger.warning(
                    "Cotacao indisponivel para %s; excluido da rentabilidade.", ativo.ticker
                )
                continue
            valor_mercado = estado.quantidade * cotacao.preco
            valor_mercado_brl += self._cambio_service.converter(
                valor_mercado, de=ativo.moeda, para="BRL"
            )

        lucro_nao_realizado_brl = valor_mercado_brl - custo_base_brl
        percentual = (
            lucro_nao_realizado_brl / custo_base_brl if custo_base_brl != 0 else Decimal(0)
        )
        return Rentabilidade(
            custo_base_brl=custo_base_brl,
            valor_mercado_brl=valor_mercado_brl,
            lucro_nao_realizado_brl=lucro_nao_realizado_brl,
            lucro_realizado_brl=lucro_realizado_brl,
            percentual=percentual,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/services/test_portfolio_service.py -v`
Expected: PASS (26 tests total)

- [ ] **Step 5: Commit**

```bash
git add src/app/domain/value_objects/rentabilidade.py src/app/services/portfolio_service.py \
  tests/unit/services/test_portfolio_service.py
```
Draft message:
```
feat(portfolio): adiciona calculo de rentabilidade no PortfolioService
```

---

## Task 6: `distribuicao()` — composição percentual por classe, setor e moeda

**Files:**
- Create: `src/app/domain/value_objects/distribuicao.py`
- Modify: `src/app/services/portfolio_service.py`
- Test: `tests/unit/services/test_portfolio_service.py` (append)

**Interfaces:**
- Consumes: `posicoes()` (Task 4).
- Produces: `Distribuicao` dataclass (`por_classe: dict[TipoAtivo, Decimal]`, `por_setor: dict[str, Decimal]`, `por_moeda: dict[str, Decimal]`, all percentuais somando 1.0); `PortfolioService.distribuicao(usuario_id) -> Distribuicao`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/services/test_portfolio_service.py — append
_VALE3 = Ativo(
    id=uuid4(),
    ticker="VALE3",
    nome="Vale ON",
    tipo=TipoAtivo.ACAO,
    setor="Mineracao",
    moeda="BRL",
    fonte_dados="manual",
)

_BTC = Ativo(
    id=uuid4(),
    ticker="BTC",
    nome="Bitcoin",
    tipo=TipoAtivo.CRIPTO,
    setor=None,
    moeda="USD",
    fonte_dados="manual",
)


def test_distribuicao_agrupa_por_classe_setor_e_moeda_somando_um():
    ativo_repository = FakeAtivoRepository()
    for ativo in (_PETR4, _VALE3, _BTC):
        ativo_repository.salvar(ativo)
    service = PortfolioService(
        FakeOperacaoRepository(),
        ativo_repository,
        FakeDadosMercadoService(
            cotacoes={
                "PETR4": _cotacao("50.00"),
                "VALE3": CotacaoAtual(
                    ticker="VALE3",
                    preco=Decimal("50.00"),
                    variacao=Decimal("0"),
                    variacao_percentual=Decimal("0"),
                    maxima_dia=Decimal("50.00"),
                    minima_dia=Decimal("50.00"),
                    volume=Decimal("0"),
                ),
                "BTC": CotacaoAtual(
                    ticker="BTC",
                    preco=Decimal("100.00"),
                    variacao=Decimal("0"),
                    variacao_percentual=Decimal("0"),
                    maxima_dia=Decimal("100.00"),
                    minima_dia=Decimal("100.00"),
                    volume=Decimal("0"),
                ),
            }
        ),
        FakeCambioService(taxa=Decimal("5.00")),
        bcb_client=None,
    )
    usuario_id = uuid4()
    for ativo_id, preco in ((_PETR4.id, "30.00"), (_VALE3.id, "30.00"), (_BTC.id, "1.00")):
        service.registrar_operacao(
            usuario_id=usuario_id,
            ativo_id=ativo_id,
            tipo=TipoOperacao.COMPRA,
            quantidade=Decimal("10"),
            preco_unitario=Decimal(preco),
            data=date(2026, 9, 1),
        )

    distribuicao = service.distribuicao(usuario_id)

    assert sum(distribuicao.por_classe.values()) == Decimal("1")
    assert sum(distribuicao.por_setor.values()) == Decimal("1")
    assert sum(distribuicao.por_moeda.values()) == Decimal("1")
    assert "N/A" in distribuicao.por_setor
    assert distribuicao.por_moeda.keys() == {"BRL", "USD"}


def test_distribuicao_sem_posicoes_retorna_dicionarios_vazios():
    service = _service_com_cotacao(preco="50.00")

    distribuicao = service.distribuicao(uuid4())

    assert distribuicao.por_classe == {}
    assert distribuicao.por_setor == {}
    assert distribuicao.por_moeda == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/services/test_portfolio_service.py -v`
Expected: FAIL — `AttributeError: 'PortfolioService' object has no attribute 'distribuicao'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/app/domain/value_objects/distribuicao.py
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.enums.tipo_ativo import TipoAtivo


@dataclass
class Distribuicao:
    por_classe: dict[TipoAtivo, Decimal]
    por_setor: dict[str, Decimal]
    por_moeda: dict[str, Decimal]
```

```python
# src/app/services/portfolio_service.py — add imports and method
from app.domain.enums.tipo_ativo import TipoAtivo
from app.domain.value_objects.distribuicao import Distribuicao

# inside class PortfolioService, below rentabilidade():

    def distribuicao(self, usuario_id: UUID) -> Distribuicao:
        posicoes = self.posicoes(usuario_id)
        total_brl = sum((p.valor_mercado_brl for p in posicoes), Decimal(0))

        por_classe: dict[TipoAtivo, Decimal] = {}
        por_setor: dict[str, Decimal] = {}
        por_moeda: dict[str, Decimal] = {}

        for posicao in posicoes:
            ativo = self._ativo_repository.buscar_por_id(posicao.ativo_id)
            fracao = posicao.valor_mercado_brl / total_brl if total_brl != 0 else Decimal(0)
            por_classe[ativo.tipo] = por_classe.get(ativo.tipo, Decimal(0)) + fracao
            setor = ativo.setor if ativo.setor is not None else "N/A"
            por_setor[setor] = por_setor.get(setor, Decimal(0)) + fracao
            por_moeda[ativo.moeda] = por_moeda.get(ativo.moeda, Decimal(0)) + fracao

        return Distribuicao(por_classe=por_classe, por_setor=por_setor, por_moeda=por_moeda)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/services/test_portfolio_service.py -v`
Expected: PASS (28 tests total)

- [ ] **Step 5: Commit**

```bash
git add src/app/domain/value_objects/distribuicao.py src/app/services/portfolio_service.py \
  tests/unit/services/test_portfolio_service.py
```
Draft message:
```
feat(portfolio): adiciona calculo de distribuicao da carteira no PortfolioService
```

---

## Task 7: `BcbClient.buscar_serie_cdi` — série diária do CDI

**Files:**
- Modify: `src/app/integrations/bcb/client.py`
- Test: `tests/unit/integrations/bcb/test_client.py` (append)

**Interfaces:**
- Consumes: nothing new — same `httpx.Client` already injected into `BcbClient`.
- Produces: `PontoCdi` dataclass (`data: date`, `valor: Decimal`); `BcbClient.buscar_serie_cdi(inicio: date, fim: date) -> list[PontoCdi]`. Task 8 imports both by these names from `app.integrations.bcb.client`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/integrations/bcb/test_client.py — append
from datetime import date

from app.integrations.bcb.client import PontoCdi


def test_buscar_serie_cdi_mapeia_pontos_diarios():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/dados/serie/bcdata.sgs.12/dados"
        assert request.url.params["dataInicial"] == "01/09/2026"
        assert request.url.params["dataFinal"] == "10/09/2026"
        return httpx.Response(
            200,
            json=[
                {"data": "01/09/2026", "valor": "0.051660"},
                {"data": "02/09/2026", "valor": "0.051660"},
            ],
        )

    client = _client(handler)

    pontos = client.buscar_serie_cdi(date(2026, 9, 1), date(2026, 9, 10))

    assert pontos == [
        PontoCdi(data=date(2026, 9, 1), valor=Decimal("0.051660")),
        PontoCdi(data=date(2026, 9, 2), valor=Decimal("0.051660")),
    ]


def test_buscar_serie_cdi_com_erro_http_lanca_bcb_indisponivel():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"message": "erro interno"})

    client = _client(handler)

    with pytest.raises(BcbIndisponivelError):
        client.buscar_serie_cdi(date(2026, 9, 1), date(2026, 9, 10))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/integrations/bcb/test_client.py -v`
Expected: FAIL — `ImportError: cannot import name 'PontoCdi'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/app/integrations/bcb/client.py — replace the top imports and add to BcbClient
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

import httpx


class BcbIndisponivelError(Exception):
    pass


@dataclass
class PontoCdi:
    data: date
    valor: Decimal


class BcbClient:
    def __init__(self, http_client: httpx.Client):
        self._http_client = http_client

    def buscar_ptax_venda(self) -> Decimal:
        dados = self._get("/dados/serie/bcdata.sgs.1/dados/ultimos/1", {"formato": "json"})
        if not dados:
            raise BcbIndisponivelError
        return Decimal(dados[0]["valor"])

    def buscar_serie_cdi(self, inicio: date, fim: date) -> list[PontoCdi]:
        dados = self._get(
            "/dados/serie/bcdata.sgs.12/dados",
            {
                "dataInicial": inicio.strftime("%d/%m/%Y"),
                "dataFinal": fim.strftime("%d/%m/%Y"),
                "formato": "json",
            },
        )
        return [
            PontoCdi(
                data=datetime.strptime(item["data"], "%d/%m/%Y").date(),
                valor=Decimal(item["valor"]),
            )
            for item in dados
        ]

    def _get(self, caminho: str, params: dict[str, str]) -> list[dict]:
        try:
            resposta = self._http_client.get(caminho, params=params)
            resposta.raise_for_status()
        except httpx.HTTPError as exc:
            raise BcbIndisponivelError from exc
        return resposta.json()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/integrations/bcb/test_client.py -v`
Expected: PASS (6 tests total: 4 existing + 2 new)

- [ ] **Step 5: Commit**

```bash
git add src/app/integrations/bcb/client.py tests/unit/integrations/bcb/test_client.py
```
Draft message:
```
feat(portfolio): adiciona busca da serie CDI no BcbClient
```

---

## Task 8: `comparativo_benchmark()` — CDI e Ibovespa

**Files:**
- Create: `src/app/domain/enums/tipo_benchmark.py`
- Create: `src/app/domain/value_objects/comparativo.py`
- Modify: `src/app/services/portfolio_service.py`
- Modify: `src/app/services/exceptions.py` (add `PortfolioVazioError`)
- Test: `tests/unit/services/test_portfolio_service.py` (append)

**Interfaces:**
- Consumes: `BcbClient.buscar_serie_cdi`/`PontoCdi` (Task 7), `DadosMercadoService.buscar_historico(ticker, periodo) -> list[PontoHistorico]` (existing), `rentabilidade()` (Task 5).
- Produces: `TipoBenchmark` enum (`CDI`, `IBOVESPA`); `Comparativo` dataclass (`benchmark`, `rentabilidade_carteira_percentual`, `rentabilidade_benchmark_percentual: Decimal | None`); `PortfolioService.comparativo_benchmark(usuario_id, benchmark) -> Comparativo`. This is the last `PortfolioService` method — Task 9 onward only wire it up, they don't add methods.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/services/test_portfolio_service.py — append
from app.domain.enums.tipo_benchmark import TipoBenchmark
from app.integrations.bcb.client import BcbIndisponivelError, PontoCdi
from app.services.exceptions import PortfolioVazioError
from app.integrations.brapi.client import PontoHistorico


class _FakeBcbClient:
    def __init__(self, pontos: list[PontoCdi] | None = None, indisponivel: bool = False):
        self._pontos = pontos if pontos is not None else []
        self.indisponivel = indisponivel

    def buscar_serie_cdi(self, inicio, fim) -> list[PontoCdi]:
        if self.indisponivel:
            raise BcbIndisponivelError
        return self._pontos


def _service_com_benchmark(bcb_client, historicos=None) -> PortfolioService:
    ativo_repository = FakeAtivoRepository()
    ativo_repository.salvar(_PETR4)
    return PortfolioService(
        FakeOperacaoRepository(),
        ativo_repository,
        FakeDadosMercadoService(
            cotacoes={"PETR4": _cotacao("50.00")}, historicos=historicos or {}
        ),
        FakeCambioService(taxa=Decimal("1")),
        bcb_client=bcb_client,
    )


def test_comparativo_benchmark_sem_operacoes_lanca_erro():
    service = _service_com_benchmark(_FakeBcbClient())

    with pytest.raises(PortfolioVazioError):
        service.comparativo_benchmark(uuid4(), TipoBenchmark.CDI)


def test_comparativo_benchmark_cdi_compoe_taxa_diaria():
    bcb_client = _FakeBcbClient(
        pontos=[
            PontoCdi(data=date(2026, 9, 1), valor=Decimal("0.05")),
            PontoCdi(data=date(2026, 9, 2), valor=Decimal("0.05")),
        ]
    )
    service = _service_com_benchmark(bcb_client)
    usuario_id = uuid4()
    service.registrar_operacao(
        usuario_id=usuario_id,
        ativo_id=_PETR4.id,
        tipo=TipoOperacao.COMPRA,
        quantidade=Decimal("10"),
        preco_unitario=Decimal("30.00"),
        data=date(2026, 9, 1),
    )

    comparativo = service.comparativo_benchmark(usuario_id, TipoBenchmark.CDI)

    taxa_esperada = (Decimal("1.0005") * Decimal("1.0005")) - Decimal("1")
    assert comparativo.benchmark == TipoBenchmark.CDI
    assert comparativo.rentabilidade_benchmark_percentual == taxa_esperada


def test_comparativo_benchmark_cdi_indisponivel_retorna_none():
    service = _service_com_benchmark(_FakeBcbClient(indisponivel=True))
    usuario_id = uuid4()
    service.registrar_operacao(
        usuario_id=usuario_id,
        ativo_id=_PETR4.id,
        tipo=TipoOperacao.COMPRA,
        quantidade=Decimal("10"),
        preco_unitario=Decimal("30.00"),
        data=date(2026, 9, 1),
    )

    comparativo = service.comparativo_benchmark(usuario_id, TipoBenchmark.CDI)

    assert comparativo.rentabilidade_benchmark_percentual is None
    assert comparativo.rentabilidade_carteira_percentual is not None


def test_comparativo_benchmark_ibovespa_usa_variacao_do_historico():
    historico = [
        PontoHistorico(
            data=datetime(2026, 9, 1, tzinfo=UTC),
            abertura=Decimal("100"),
            maxima=Decimal("100"),
            minima=Decimal("100"),
            fechamento=Decimal("100"),
            volume=Decimal("0"),
        ),
        PontoHistorico(
            data=datetime(2026, 9, 10, tzinfo=UTC),
            abertura=Decimal("110"),
            maxima=Decimal("110"),
            minima=Decimal("110"),
            fechamento=Decimal("110"),
            volume=Decimal("0"),
        ),
    ]
    service = _service_com_benchmark(_FakeBcbClient(), historicos={"^BVSP": historico})
    usuario_id = uuid4()
    service.registrar_operacao(
        usuario_id=usuario_id,
        ativo_id=_PETR4.id,
        tipo=TipoOperacao.COMPRA,
        quantidade=Decimal("10"),
        preco_unitario=Decimal("30.00"),
        data=date(2026, 9, 1),
    )

    comparativo = service.comparativo_benchmark(usuario_id, TipoBenchmark.IBOVESPA)

    assert comparativo.rentabilidade_benchmark_percentual == Decimal("0.10")


def test_comparativo_benchmark_ibovespa_indisponivel_retorna_none():
    service = _service_com_benchmark(_FakeBcbClient(), historicos={})
    usuario_id = uuid4()
    service.registrar_operacao(
        usuario_id=usuario_id,
        ativo_id=_PETR4.id,
        tipo=TipoOperacao.COMPRA,
        quantidade=Decimal("10"),
        preco_unitario=Decimal("30.00"),
        data=date(2026, 9, 1),
    )

    comparativo = service.comparativo_benchmark(usuario_id, TipoBenchmark.IBOVESPA)

    assert comparativo.rentabilidade_benchmark_percentual is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/services/test_portfolio_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.domain.enums.tipo_benchmark'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/app/domain/enums/tipo_benchmark.py
from enum import Enum


class TipoBenchmark(str, Enum):
    CDI = "CDI"
    IBOVESPA = "IBOVESPA"
```

```python
# src/app/domain/value_objects/comparativo.py
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.enums.tipo_benchmark import TipoBenchmark


@dataclass
class Comparativo:
    benchmark: TipoBenchmark
    rentabilidade_carteira_percentual: Decimal
    rentabilidade_benchmark_percentual: Decimal | None
```

```python
# src/app/services/exceptions.py — append
class PortfolioVazioError(Exception):
    pass
```

```python
# src/app/services/portfolio_service.py — add imports and methods
from app.domain.enums.periodo_historico import PeriodoHistorico
from app.domain.enums.tipo_benchmark import TipoBenchmark
from app.domain.value_objects.comparativo import Comparativo
from app.integrations.bcb.client import BcbIndisponivelError
from app.services.exceptions import PortfolioVazioError

# inside class PortfolioService, below distribuicao():

    def comparativo_benchmark(self, usuario_id: UUID, benchmark: TipoBenchmark) -> Comparativo:
        operacoes = self._operacao_repository.listar_por_usuario(usuario_id)
        if not operacoes:
            raise PortfolioVazioError(usuario_id)

        data_inicio = min(op.data for op in operacoes)
        rentabilidade_carteira = self.rentabilidade(usuario_id).percentual

        if benchmark == TipoBenchmark.CDI:
            rentabilidade_benchmark = self._rentabilidade_cdi(data_inicio)
        else:
            rentabilidade_benchmark = self._rentabilidade_ibovespa(data_inicio)

        return Comparativo(
            benchmark=benchmark,
            rentabilidade_carteira_percentual=rentabilidade_carteira,
            rentabilidade_benchmark_percentual=rentabilidade_benchmark,
        )

    def _rentabilidade_cdi(self, data_inicio: date) -> Decimal | None:
        try:
            pontos = self._bcb_client.buscar_serie_cdi(data_inicio, date.today())
        except BcbIndisponivelError:
            logger.warning("CDI indisponivel; comparativo de benchmark sem CDI.")
            return None

        fator = Decimal(1)
        for ponto in pontos:
            fator *= Decimal(1) + ponto.valor / Decimal(100)
        return fator - Decimal(1)

    def _rentabilidade_ibovespa(self, data_inicio: date) -> Decimal | None:
        periodo = _periodo_desde(data_inicio)
        try:
            pontos = self._dados_mercado_service.buscar_historico("^BVSP", periodo)
        except (BrapiIndisponivelError, TickerNaoEncontradoError):
            logger.warning("Ibovespa indisponivel; comparativo de benchmark sem Ibovespa.")
            return None
        if not pontos:
            return None
        return (pontos[-1].fechamento - pontos[0].fechamento) / pontos[0].fechamento


def _periodo_desde(data_inicio: date) -> PeriodoHistorico:
    dias = (date.today() - data_inicio).days
    if dias <= 1:
        return PeriodoHistorico.UM_DIA
    if dias <= 7:
        return PeriodoHistorico.UMA_SEMANA
    if dias <= 30:
        return PeriodoHistorico.UM_MES
    if dias <= 90:
        return PeriodoHistorico.TRES_MESES
    if dias <= 365:
        return PeriodoHistorico.UM_ANO
    return PeriodoHistorico.CINCO_ANOS
```

`_periodo_desde` is a module-level function (mirrors `replay_operacoes`), placed after the `PortfolioService` class body.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/services/test_portfolio_service.py -v`
Expected: PASS (33 tests total)

- [ ] **Step 5: Commit**

```bash
git add src/app/domain/enums/tipo_benchmark.py src/app/domain/value_objects/comparativo.py \
  src/app/services/portfolio_service.py src/app/services/exceptions.py \
  tests/unit/services/test_portfolio_service.py
```
Draft message:
```
feat(portfolio): adiciona comparativo com benchmark no PortfolioService
```

---

## Task 9: `api/deps.py` — dependências do PortfolioService

**Files:**
- Modify: `src/app/api/deps.py`

**Interfaces:**
- Consumes: `SqlAlchemyOperacaoRepository` (Task 1), `PortfolioService` (Tasks 3–8), existing `get_ativo_repository`, `get_dados_mercado_service`, `get_cambio_service`, `get_bcb_client`.
- Produces: `get_operacao_repository(session) -> OperacaoRepository`, `get_portfolio_service(...) -> PortfolioService`. Task 11's controller imports both by name.

This task has no independent test — `deps.py` is composition wiring, following the same convention already used for `get_alerta_service`/`get_notificacao_service` (no dedicated unit test for dependency providers in this codebase). It is exercised indirectly by Task 11's controller once wired.

- [ ] **Step 1: Add the new imports to `src/app/api/deps.py`**

```python
from app.repositories.interfaces.operacao_repository import OperacaoRepository
from app.repositories.sqlalchemy.operacao_repository import SqlAlchemyOperacaoRepository
from app.services.portfolio_service import PortfolioService
```

Add each import in its already-alphabetized group (next to `AlertaRepository`/`SqlAlchemyAlertaRepository`/`AlertaService` respectively).

- [ ] **Step 2: Add the two provider functions**, right after `get_alerta_service`:

```python
def get_operacao_repository(
    session: Session = Depends(get_db_session),
) -> OperacaoRepository:
    return SqlAlchemyOperacaoRepository(session)


def get_portfolio_service(
    operacao_repository: OperacaoRepository = Depends(get_operacao_repository),
    ativo_repository: AtivoRepository = Depends(get_ativo_repository),
    dados_mercado_service: DadosMercadoService = Depends(get_dados_mercado_service),
    cambio_service: CambioService = Depends(get_cambio_service),
    bcb_client: BcbClient = Depends(get_bcb_client),
) -> PortfolioService:
    return PortfolioService(
        operacao_repository, ativo_repository, dados_mercado_service, cambio_service, bcb_client
    )
```

- [ ] **Step 3: Verify the app still imports cleanly**

Run: `.venv/bin/python -c "from app.main import app"`
Expected: no exception (confirms no circular import or typo before the controller exists in Task 11 to actually use these).

- [ ] **Step 4: Commit**

```bash
git add src/app/api/deps.py
```
Draft message:
```
feat(portfolio): registra dependencias do PortfolioService na API
```

---

## Task 10: Schemas REST (`portfolio.py`)

**Files:**
- Create: `src/app/api/v1/schemas/portfolio.py`

**Interfaces:**
- Consumes: `Operacao`, `TipoOperacao` (existing); `Posicao`, `Rentabilidade`, `Comparativo`, `Distribuicao`, `TipoBenchmark` (Tasks 4/5/8/6).
- Produces: `RegistrarOperacaoRequest`, `OperacaoResponse`, `PosicaoResponse`, `RentabilidadeResponse`, `ComparativoResponse`, `DistribuicaoResponse` — each response has a `.de(...)` static constructor. Task 11's controller imports all six by these names.

No dedicated test for this task — Pydantic schemas here are pure data mapping with no branching logic, same convention as `schemas/alerta.py` (not unit-tested on its own; exercised through the controller). Task 11 exercises it end-to-end.

- [ ] **Step 1: Write the schemas**

```python
# src/app/api/v1/schemas/portfolio.py
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.entities.operacao import Operacao
from app.domain.enums.tipo_ativo import TipoAtivo
from app.domain.enums.tipo_benchmark import TipoBenchmark
from app.domain.enums.tipo_operacao import TipoOperacao
from app.domain.value_objects.comparativo import Comparativo
from app.domain.value_objects.distribuicao import Distribuicao
from app.domain.value_objects.posicao import Posicao
from app.domain.value_objects.rentabilidade import Rentabilidade


class RegistrarOperacaoRequest(BaseModel):
    ativo_id: UUID
    tipo: TipoOperacao
    quantidade: Decimal = Field(gt=0)
    preco_unitario: Decimal = Field(gt=0)
    data: date


class OperacaoResponse(BaseModel):
    id: UUID
    ativo_id: UUID
    tipo: TipoOperacao
    quantidade: Decimal
    preco_unitario: Decimal
    data: date
    criado_em: datetime

    @staticmethod
    def de(operacao: Operacao) -> "OperacaoResponse":
        return OperacaoResponse(
            id=operacao.id,
            ativo_id=operacao.ativo_id,
            tipo=operacao.tipo,
            quantidade=operacao.quantidade,
            preco_unitario=operacao.preco_unitario,
            data=operacao.data,
            criado_em=operacao.criado_em,
        )


class PosicaoResponse(BaseModel):
    ativo_id: UUID
    ticker: str
    quantidade: Decimal
    preco_medio: Decimal
    cotacao_atual: Decimal
    valor_mercado: Decimal
    valor_mercado_brl: Decimal
    lucro_nao_realizado: Decimal
    lucro_realizado: Decimal

    @staticmethod
    def de(posicao: Posicao) -> "PosicaoResponse":
        return PosicaoResponse(
            ativo_id=posicao.ativo_id,
            ticker=posicao.ticker,
            quantidade=posicao.quantidade,
            preco_medio=posicao.preco_medio,
            cotacao_atual=posicao.cotacao_atual,
            valor_mercado=posicao.valor_mercado,
            valor_mercado_brl=posicao.valor_mercado_brl,
            lucro_nao_realizado=posicao.lucro_nao_realizado,
            lucro_realizado=posicao.lucro_realizado,
        )


class RentabilidadeResponse(BaseModel):
    custo_base_brl: Decimal
    valor_mercado_brl: Decimal
    lucro_nao_realizado_brl: Decimal
    lucro_realizado_brl: Decimal
    percentual: Decimal

    @staticmethod
    def de(rentabilidade: Rentabilidade) -> "RentabilidadeResponse":
        return RentabilidadeResponse(
            custo_base_brl=rentabilidade.custo_base_brl,
            valor_mercado_brl=rentabilidade.valor_mercado_brl,
            lucro_nao_realizado_brl=rentabilidade.lucro_nao_realizado_brl,
            lucro_realizado_brl=rentabilidade.lucro_realizado_brl,
            percentual=rentabilidade.percentual,
        )


class ComparativoResponse(BaseModel):
    benchmark: TipoBenchmark
    rentabilidade_carteira_percentual: Decimal
    rentabilidade_benchmark_percentual: Decimal | None

    @staticmethod
    def de(comparativo: Comparativo) -> "ComparativoResponse":
        return ComparativoResponse(
            benchmark=comparativo.benchmark,
            rentabilidade_carteira_percentual=comparativo.rentabilidade_carteira_percentual,
            rentabilidade_benchmark_percentual=comparativo.rentabilidade_benchmark_percentual,
        )


class DistribuicaoResponse(BaseModel):
    por_classe: dict[TipoAtivo, Decimal]
    por_setor: dict[str, Decimal]
    por_moeda: dict[str, Decimal]

    @staticmethod
    def de(distribuicao: Distribuicao) -> "DistribuicaoResponse":
        return DistribuicaoResponse(
            por_classe=distribuicao.por_classe,
            por_setor=distribuicao.por_setor,
            por_moeda=distribuicao.por_moeda,
        )
```

- [ ] **Step 2: Verify it imports cleanly**

Run: `.venv/bin/python -c "from app.api.v1.schemas.portfolio import OperacaoResponse"`
Expected: no exception

- [ ] **Step 3: Commit**

```bash
git add src/app/api/v1/schemas/portfolio.py
```
Draft message:
```
feat(portfolio): adiciona schemas REST do portfolio
```

---

## Task 11: Controller REST e registro no `main.py`

**Files:**
- Create: `src/app/api/v1/controllers/portfolio.py`
- Modify: `src/app/main.py`
- Test: `tests/unit/services/test_portfolio_service.py` is NOT touched here — this task has no dedicated automated test (see note below), but ends with a manual smoke check.

**Interfaces:**
- Consumes: everything from Tasks 1–10.
- Produces: `router` (FastAPI `APIRouter`) exposing the 7 endpoints from the spec.

This codebase has no HTTP-level controller test for `alertas.py` or `notificacoes.py` either (confirmed: `tests/unit/api/` only covers usuarios/auth/watchlist/ativos/cotacao/indicador/sinal controllers) — service-level unit tests plus a manual smoke check is the established bar for this kind of controller. Follow that convention here rather than introducing a new one for this vertical alone.

- [ ] **Step 1: Write the controller**

```python
# src/app/api/v1/controllers/portfolio.py
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_portfolio_service, get_usuario_atual
from app.api.v1.schemas.portfolio import (
    ComparativoResponse,
    DistribuicaoResponse,
    OperacaoResponse,
    PosicaoResponse,
    RegistrarOperacaoRequest,
    RentabilidadeResponse,
)
from app.domain.entities.usuario import Usuario
from app.domain.enums.tipo_benchmark import TipoBenchmark
from app.services.exceptions import (
    AtivoNaoEncontradoError,
    OperacaoInvalidaError,
    OperacaoNaoEncontradaError,
    PortfolioVazioError,
    QuantidadeInsuficienteError,
)
from app.services.portfolio_service import PortfolioService

router = APIRouter(tags=["portfolio"])


@router.post("/operacoes", status_code=status.HTTP_201_CREATED, response_model=OperacaoResponse)
def registrar_operacao(
    dados: RegistrarOperacaoRequest,
    usuario: Usuario = Depends(get_usuario_atual),
    service: PortfolioService = Depends(get_portfolio_service),
) -> OperacaoResponse:
    try:
        operacao = service.registrar_operacao(
            usuario_id=usuario.id,
            ativo_id=dados.ativo_id,
            tipo=dados.tipo,
            quantidade=dados.quantidade,
            preco_unitario=dados.preco_unitario,
            data=dados.data,
        )
    except AtivoNaoEncontradoError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ativo nao encontrado") from exc
    except (OperacaoInvalidaError, QuantidadeInsuficienteError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    return OperacaoResponse.de(operacao)


@router.get("/operacoes", response_model=list[OperacaoResponse])
def listar_operacoes(
    usuario: Usuario = Depends(get_usuario_atual),
    service: PortfolioService = Depends(get_portfolio_service),
) -> list[OperacaoResponse]:
    return [OperacaoResponse.de(op) for op in service.listar_operacoes(usuario.id)]


@router.delete("/operacoes/{operacao_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_operacao(
    operacao_id: UUID,
    usuario: Usuario = Depends(get_usuario_atual),
    service: PortfolioService = Depends(get_portfolio_service),
) -> None:
    try:
        service.remover_operacao(usuario.id, operacao_id)
    except OperacaoNaoEncontradaError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Operacao nao encontrada") from exc


@router.get("/portfolio/posicoes", response_model=list[PosicaoResponse])
def posicoes(
    usuario: Usuario = Depends(get_usuario_atual),
    service: PortfolioService = Depends(get_portfolio_service),
) -> list[PosicaoResponse]:
    return [PosicaoResponse.de(p) for p in service.posicoes(usuario.id)]


@router.get("/portfolio/rentabilidade", response_model=RentabilidadeResponse)
def rentabilidade(
    usuario: Usuario = Depends(get_usuario_atual),
    service: PortfolioService = Depends(get_portfolio_service),
) -> RentabilidadeResponse:
    return RentabilidadeResponse.de(service.rentabilidade(usuario.id))


@router.get("/portfolio/benchmark", response_model=ComparativoResponse)
def comparativo_benchmark(
    benchmark: TipoBenchmark,
    usuario: Usuario = Depends(get_usuario_atual),
    service: PortfolioService = Depends(get_portfolio_service),
) -> ComparativoResponse:
    try:
        comparativo = service.comparativo_benchmark(usuario.id, benchmark)
    except PortfolioVazioError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nenhuma operacao registrada") from exc

    return ComparativoResponse.de(comparativo)


@router.get("/portfolio/distribuicao", response_model=DistribuicaoResponse)
def distribuicao(
    usuario: Usuario = Depends(get_usuario_atual),
    service: PortfolioService = Depends(get_portfolio_service),
) -> DistribuicaoResponse:
    return DistribuicaoResponse.de(service.distribuicao(usuario.id))
```

- [ ] **Step 2: Register the router in `main.py`**

```python
# src/app/main.py — add import
from app.api.v1.controllers.portfolio import router as portfolio_router

# and add this line next to the other app.include_router(...) calls
app.include_router(portfolio_router, prefix="/api/v1")
```

- [ ] **Step 3: Smoke-check the app boots and the routes exist**

Run: `.venv/bin/python -c "from app.main import app; print(sorted(r.path for r in app.routes if 'portfolio' in r.path or 'operacoes' in r.path))"`
Expected output includes: `/api/v1/operacoes`, `/api/v1/operacoes/{operacao_id}`, `/api/v1/portfolio/benchmark`, `/api/v1/portfolio/distribuicao`, `/api/v1/portfolio/posicoes`, `/api/v1/portfolio/rentabilidade`

- [ ] **Step 4: Run the full unit suite once to confirm nothing else broke**

Run: `.venv/bin/pytest tests/unit -v`
Expected: PASS, all tests including the 33 `test_portfolio_service.py` tests and the 6 `test_client.py` (BCB) tests from earlier tasks.

- [ ] **Step 5: Commit**

```bash
git add src/app/api/v1/controllers/portfolio.py src/app/main.py
```
Draft message:
```
feat(portfolio): expoe endpoints REST de operacoes e portfolio
```

---

## Final check (after Task 11)

Run the full suite once more end to end:
- `.venv/bin/pytest tests/unit -v` — no DB required.
- `docker compose up -d postgres redis` then `.venv/bin/pytest tests/ -m integration -v` — covers Task 1's `test_operacao_repository.py` plus all pre-existing integration tests, confirming the new migration/model didn't break anything already in place.
- `.venv/bin/ruff check src tests` — style/lint check used elsewhere in this repo.
