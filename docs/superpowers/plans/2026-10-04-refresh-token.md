# Refresh token Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar refresh token persistido com rotação e detecção de reuso (RNF-04): emissão no cadastro e no login, `POST /auth/refresh` e `POST /auth/logout`.

**Architecture:** Entidade `RefreshToken` + repositório (ABC, SQLAlchemy, Fake) guardando só o SHA-256 do token opaco. Um `RefreshTokenService` emite, rotaciona e revoga por família, usando o `criar_token` já existente para o access token. Os controllers de cadastro e login passam a usar o service; `TokenResponse` só ganha campos.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, python-jose, pytest.

**Spec:** `docs/superpowers/specs/2026-10-04-refresh-token-design.md`

## Global Constraints

- Zero comentários no código e nos testes. Nomes de domínio e de teste em português, sem acentos em identificadores.
- Usar `.venv/bin/pytest`, `.venv/bin/ruff`, `.venv/bin/alembic`. Formatar só os arquivos tocados (`.venv/bin/ruff format <arquivos>`).
- Token opaco: `secrets.token_urlsafe(48)`. No banco, só `hashlib.sha256(token.encode()).hexdigest()` (64 caracteres).
- Validade padrão: access 30 minutos (`jwt_expiration_minutes = 30`), refresh 30 dias (`refresh_token_expiracao_dias = 30`).
- Token expirado quando `agora >= expira_em`.
- Migration nova com `down_revision = "c9e3a5b7d1f2"`.
- Todo repositório tem ABC + SQLAlchemy + Fake, adicionados juntos.
- O usuário comita pessoalmente: nos passos de commit, apenas `git add` e a mensagem proposta (Português, Conventional Commits com escopo, terminando com `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`).
- Testes de integração precisam de Postgres. A porta 5432 desta máquina é de outro projeto: suba um descartável com `docker run -d --rm --name pg-refresh -e POSTGRES_USER=insightflow -e POSTGRES_PASSWORD=insightflow -e POSTGRES_DB=insightflow_test -p 5434:5432 postgres:16` e use `TEST_DATABASE_URL=postgresql://insightflow:insightflow@localhost:5434/insightflow_test`.

## Review Focus

1. **Expiração exatamente no limite (`agora == expira_em`)** — deve contar como expirado. Teste na Task 1.
2. **Datas vindas do Postgres** — `expira_em`/`revogado_em` precisam voltar timezone-aware; comparar aware com naive lança `TypeError` (500 no refresh). Teste na Task 3.
3. **Refresh depois do logout** — deve dar 401, mesmo com o token ainda dentro da validade. Teste na Task 4.
4. **Reuso derruba o token já rotacionado** — o atacante que reusa o antigo também invalida o novo do usuário legítimo. Teste na Task 2 (service) e na Task 4 (API).
5. **Corpo sem `refresh_token`** — 422, não 500. Teste na Task 4.

---

## File Structure

| Arquivo | Responsabilidade |
|---|---|
| `src/app/domain/entities/refresh_token.py` (novo) | Entidade `RefreshToken` |
| `src/app/repositories/interfaces/refresh_token_repository.py` (novo) | ABC |
| `tests/fixtures/fake_refresh_token_repository.py` (novo) | Fake |
| `src/app/services/refresh_token_service.py` (novo) | `ParTokens`, `RefreshTokenService` |
| `src/app/services/exceptions.py` | `RefreshTokenInvalidoError` |
| `src/app/db/models/refresh_token.py` (novo) | `RefreshTokenModel` |
| `src/app/repositories/sqlalchemy/refresh_token_repository.py` (novo) | Implementação SQLAlchemy |
| `alembic/versions/f1a7c3e9b2d4_cria_tabela_refresh_tokens.py` (novo) | Migration |
| `alembic/env.py`, `tests/integration/conftest.py` | Importam o novo model |
| `src/app/core/config.py`, `.env.example` | Validades |
| `src/app/api/v1/schemas/token.py`, `src/app/api/v1/schemas/auth.py` | `TokenResponse` ampliado, `RefreshRequest` |
| `src/app/api/deps.py` | `get_refresh_token_repository`, `get_refresh_token_service` |
| `src/app/api/v1/controllers/auth.py`, `usuarios.py` | Endpoints |
| `tests/unit/api/conftest.py` | Override do repositório fake |

---

### Task 1: Entidade, ABC, Fake e exceção

**Files:**
- Create: `src/app/domain/entities/refresh_token.py`
- Create: `src/app/repositories/interfaces/refresh_token_repository.py`
- Create: `tests/fixtures/fake_refresh_token_repository.py`
- Modify: `src/app/services/exceptions.py`
- Test: `tests/unit/domain/entities/test_refresh_token.py`

**Interfaces:**
- Produces: `RefreshToken(id, usuario_id, token_hash, familia_id, criado_em, expira_em, revogado_em=None)` com `esta_expirado(agora) -> bool`, `esta_revogado() -> bool`, `revogar(agora) -> None`; `RefreshTokenRepository` com `salvar`, `buscar_por_hash`, `revogar_familia(familia_id, revogado_em)`; `FakeRefreshTokenRepository` (+ `listar_todos() -> list[RefreshToken]`); `RefreshTokenInvalidoError(Exception)`.

- [ ] **Step 1: Write the failing test**

`tests/unit/domain/entities/test_refresh_token.py`:

```python
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.domain.entities.refresh_token import RefreshToken

_AGORA = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)


def _token(expira_em: datetime = _AGORA + timedelta(days=30)) -> RefreshToken:
    return RefreshToken(
        id=uuid4(),
        usuario_id=uuid4(),
        token_hash="a" * 64,
        familia_id=uuid4(),
        criado_em=_AGORA,
        expira_em=expira_em,
    )


def test_token_dentro_da_validade_nao_esta_expirado():
    assert _token().esta_expirado(_AGORA) is False


def test_token_no_instante_de_expiracao_esta_expirado():
    assert _token(expira_em=_AGORA).esta_expirado(_AGORA) is True


def test_revogar_marca_o_instante_e_o_token_fica_revogado():
    token = _token()

    token.revogar(_AGORA)

    assert token.esta_revogado() is True
    assert token.revogado_em == _AGORA


def test_token_novo_nao_esta_revogado():
    assert _token().esta_revogado() is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/domain/entities/test_refresh_token.py -q`
Expected: `ModuleNotFoundError: No module named 'app.domain.entities.refresh_token'`.

- [ ] **Step 3: Write minimal implementation**

`src/app/domain/entities/refresh_token.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class RefreshToken:
    id: UUID
    usuario_id: UUID
    token_hash: str
    familia_id: UUID
    criado_em: datetime
    expira_em: datetime
    revogado_em: datetime | None = None

    def esta_expirado(self, agora: datetime) -> bool:
        return agora >= self.expira_em

    def esta_revogado(self) -> bool:
        return self.revogado_em is not None

    def revogar(self, agora: datetime) -> None:
        self.revogado_em = agora
```

`src/app/repositories/interfaces/refresh_token_repository.py`:

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from app.domain.entities.refresh_token import RefreshToken


class RefreshTokenRepository(ABC):
    @abstractmethod
    def salvar(self, token: RefreshToken) -> None: ...

    @abstractmethod
    def buscar_por_hash(self, token_hash: str) -> RefreshToken | None: ...

    @abstractmethod
    def revogar_familia(self, familia_id: UUID, revogado_em: datetime) -> None: ...
```

`tests/fixtures/fake_refresh_token_repository.py`:

```python
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.domain.entities.refresh_token import RefreshToken
from app.repositories.interfaces.refresh_token_repository import RefreshTokenRepository


class FakeRefreshTokenRepository(RefreshTokenRepository):
    def __init__(self) -> None:
        self._tokens: dict[UUID, RefreshToken] = {}

    def salvar(self, token: RefreshToken) -> None:
        self._tokens[token.id] = token

    def buscar_por_hash(self, token_hash: str) -> RefreshToken | None:
        return next((t for t in self._tokens.values() if t.token_hash == token_hash), None)

    def revogar_familia(self, familia_id: UUID, revogado_em: datetime) -> None:
        for token in self._tokens.values():
            if token.familia_id == familia_id and not token.esta_revogado():
                token.revogar(revogado_em)

    def listar_todos(self) -> list[RefreshToken]:
        return list(self._tokens.values())
```

Ao fim de `src/app/services/exceptions.py`:

```python
class RefreshTokenInvalidoError(Exception):
    pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit -q && .venv/bin/ruff check src tests`
Expected: todos passam.

- [ ] **Step 5: Commit**

```bash
git add src/app/domain/entities/refresh_token.py src/app/repositories/interfaces/refresh_token_repository.py tests/fixtures/fake_refresh_token_repository.py src/app/services/exceptions.py tests/unit/domain/entities/test_refresh_token.py
```

Mensagem: `feat(auth): adiciona entidade e repositorio de RefreshToken`

---

### Task 2: RefreshTokenService

**Files:**
- Create: `src/app/services/refresh_token_service.py`
- Test: `tests/unit/services/test_refresh_token_service.py`

**Interfaces:**
- Consumes: Task 1 inteira; `FakeUsuarioRepository` (`tests/fixtures/fake_usuario_repository.py`); `Usuario.criar(id, nome, email, senha, criado_em)`; `core.security.criar_token(usuario_id, secret_key, expiracao_minutos)` e `decodificar_token(token, secret_key) -> UUID`.
- Produces: `ParTokens(access_token: str, refresh_token: str, expires_in: int)`; `RefreshTokenService(refresh_token_repository, usuario_repository, jwt_secret_key: str, access_expiracao_minutos: int, refresh_expiracao_dias: int, agora: Callable[[], datetime] = ...)` com `emitir(usuario_id) -> ParTokens`, `renovar(refresh_token: str) -> ParTokens`, `revogar(refresh_token: str) -> None`.

- [ ] **Step 1: Write the failing tests**

`tests/unit/services/test_refresh_token_service.py`:

```python
import hashlib
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.core.security import decodificar_token
from app.domain.entities.usuario import Usuario
from app.services.exceptions import RefreshTokenInvalidoError
from app.services.refresh_token_service import RefreshTokenService
from tests.fixtures.fake_refresh_token_repository import FakeRefreshTokenRepository
from tests.fixtures.fake_usuario_repository import FakeUsuarioRepository

_SEGREDO = "segredo-de-teste"
_INICIO = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)


class _Relogio:
    def __init__(self) -> None:
        self.agora = _INICIO

    def __call__(self) -> datetime:
        return self.agora


def _cenario(ativo: bool = True):
    usuarios = FakeUsuarioRepository()
    usuario = Usuario.criar(
        id=uuid4(), nome="Ana", email="ana@example.com", senha="segredo123", criado_em=_INICIO
    )
    usuario.ativo = ativo
    usuarios.salvar(usuario)
    tokens = FakeRefreshTokenRepository()
    relogio = _Relogio()
    service = RefreshTokenService(
        tokens,
        usuarios,
        jwt_secret_key=_SEGREDO,
        access_expiracao_minutos=30,
        refresh_expiracao_dias=30,
        agora=relogio,
    )
    return service, tokens, usuario, relogio


def test_emitir_grava_so_o_hash_e_o_access_decodifica_para_o_usuario():
    service, tokens, usuario, _ = _cenario()

    par = service.emitir(usuario.id)

    salvos = tokens.listar_todos()
    assert len(salvos) == 1
    assert salvos[0].token_hash == hashlib.sha256(par.refresh_token.encode()).hexdigest()
    assert par.refresh_token not in {t.token_hash for t in salvos}
    assert salvos[0].expira_em == _INICIO + timedelta(days=30)
    assert decodificar_token(par.access_token, _SEGREDO) == usuario.id
    assert par.expires_in == 1800


def test_renovar_rotaciona_na_mesma_familia():
    service, tokens, usuario, _ = _cenario()
    primeiro = service.emitir(usuario.id)

    segundo = service.renovar(primeiro.refresh_token)

    assert segundo.refresh_token != primeiro.refresh_token
    assert decodificar_token(segundo.access_token, _SEGREDO) == usuario.id
    antigo = tokens.buscar_por_hash(hashlib.sha256(primeiro.refresh_token.encode()).hexdigest())
    novo = tokens.buscar_por_hash(hashlib.sha256(segundo.refresh_token.encode()).hexdigest())
    assert antigo.esta_revogado() is True
    assert novo.esta_revogado() is False
    assert novo.familia_id == antigo.familia_id


def test_reuso_de_token_revogado_derruba_a_familia_inclusive_o_token_rotacionado():
    service, _, usuario, _ = _cenario()
    primeiro = service.emitir(usuario.id)
    segundo = service.renovar(primeiro.refresh_token)

    with pytest.raises(RefreshTokenInvalidoError):
        service.renovar(primeiro.refresh_token)
    with pytest.raises(RefreshTokenInvalidoError):
        service.renovar(segundo.refresh_token)


def test_token_expirado_e_invalido():
    service, _, usuario, relogio = _cenario()
    par = service.emitir(usuario.id)
    relogio.agora = _INICIO + timedelta(days=30)

    with pytest.raises(RefreshTokenInvalidoError):
        service.renovar(par.refresh_token)


def test_token_inexistente_e_invalido():
    service, _, _, _ = _cenario()

    with pytest.raises(RefreshTokenInvalidoError):
        service.renovar("token-que-nunca-existiu")


def test_usuario_inativo_nao_renova():
    service, _, usuario, _ = _cenario(ativo=False)
    par = service.emitir(usuario.id)

    with pytest.raises(RefreshTokenInvalidoError):
        service.renovar(par.refresh_token)


def test_revogar_derruba_a_familia():
    service, _, usuario, _ = _cenario()
    primeiro = service.emitir(usuario.id)
    segundo = service.renovar(primeiro.refresh_token)

    service.revogar(segundo.refresh_token)

    with pytest.raises(RefreshTokenInvalidoError):
        service.renovar(segundo.refresh_token)


def test_revogar_token_desconhecido_nao_lanca_erro():
    service, _, _, _ = _cenario()

    service.revogar("token-que-nunca-existiu")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/services/test_refresh_token_service.py -q`
Expected: `ModuleNotFoundError: No module named 'app.services.refresh_token_service'`.

- [ ] **Step 3: Write minimal implementation**

`src/app/services/refresh_token_service.py`:

```python
from __future__ import annotations

import hashlib
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.core.security import criar_token
from app.domain.entities.refresh_token import RefreshToken
from app.repositories.interfaces.refresh_token_repository import RefreshTokenRepository
from app.repositories.interfaces.usuario_repository import UsuarioRepository
from app.services.exceptions import RefreshTokenInvalidoError


@dataclass
class ParTokens:
    access_token: str
    refresh_token: str
    expires_in: int


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class RefreshTokenService:
    def __init__(
        self,
        refresh_token_repository: RefreshTokenRepository,
        usuario_repository: UsuarioRepository,
        jwt_secret_key: str,
        access_expiracao_minutos: int,
        refresh_expiracao_dias: int,
        agora: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self._refresh_token_repository = refresh_token_repository
        self._usuario_repository = usuario_repository
        self._jwt_secret_key = jwt_secret_key
        self._access_expiracao_minutos = access_expiracao_minutos
        self._refresh_expiracao_dias = refresh_expiracao_dias
        self._agora = agora

    def emitir(self, usuario_id: UUID) -> ParTokens:
        return self._emitir_na_familia(usuario_id, uuid4())

    def renovar(self, refresh_token: str) -> ParTokens:
        agora = self._agora()
        token = self._refresh_token_repository.buscar_por_hash(_hash(refresh_token))
        if token is None:
            raise RefreshTokenInvalidoError
        if token.esta_revogado():
            self._refresh_token_repository.revogar_familia(token.familia_id, agora)
            raise RefreshTokenInvalidoError
        if token.esta_expirado(agora):
            raise RefreshTokenInvalidoError
        usuario = self._usuario_repository.buscar_por_id(token.usuario_id)
        if usuario is None or not usuario.ativo:
            raise RefreshTokenInvalidoError

        token.revogar(agora)
        self._refresh_token_repository.salvar(token)
        return self._emitir_na_familia(token.usuario_id, token.familia_id)

    def revogar(self, refresh_token: str) -> None:
        token = self._refresh_token_repository.buscar_por_hash(_hash(refresh_token))
        if token is not None:
            self._refresh_token_repository.revogar_familia(token.familia_id, self._agora())

    def _emitir_na_familia(self, usuario_id: UUID, familia_id: UUID) -> ParTokens:
        agora = self._agora()
        refresh_token = secrets.token_urlsafe(48)
        self._refresh_token_repository.salvar(
            RefreshToken(
                id=uuid4(),
                usuario_id=usuario_id,
                token_hash=_hash(refresh_token),
                familia_id=familia_id,
                criado_em=agora,
                expira_em=agora + timedelta(days=self._refresh_expiracao_dias),
            )
        )
        return ParTokens(
            access_token=criar_token(
                usuario_id, self._jwt_secret_key, self._access_expiracao_minutos
            ),
            refresh_token=refresh_token,
            expires_in=self._access_expiracao_minutos * 60,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit -q && .venv/bin/ruff check src tests`
Expected: todos passam.

- [ ] **Step 5: Commit**

```bash
git add src/app/services/refresh_token_service.py tests/unit/services/test_refresh_token_service.py
```

Mensagem: `feat(auth): adiciona RefreshTokenService com rotacao e deteccao de reuso`

---

### Task 3: Persistência (model, repositório SQLAlchemy, migration)

**Files:**
- Create: `src/app/db/models/refresh_token.py`
- Create: `src/app/repositories/sqlalchemy/refresh_token_repository.py`
- Create: `alembic/versions/f1a7c3e9b2d4_cria_tabela_refresh_tokens.py`
- Modify: `alembic/env.py` (import do model, junto dos outros)
- Modify: `tests/integration/conftest.py` (import do model, junto dos outros)
- Test: `tests/integration/repositories/test_refresh_token_repository.py`

**Interfaces:**
- Consumes: `RefreshToken`, `RefreshTokenRepository` (Task 1).
- Produces: `RefreshTokenModel`; `SqlAlchemyRefreshTokenRepository(session)`.

- [ ] **Step 1: Write the failing tests**

`tests/integration/repositories/test_refresh_token_repository.py`:

```python
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.domain.entities.refresh_token import RefreshToken
from app.domain.entities.usuario import Usuario
from app.repositories.sqlalchemy.refresh_token_repository import SqlAlchemyRefreshTokenRepository
from app.repositories.sqlalchemy.usuario_repository import SqlAlchemyUsuarioRepository

pytestmark = pytest.mark.integration

_AGORA = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)


def _novo_usuario(session) -> Usuario:
    usuario = Usuario.criar(
        id=uuid4(),
        nome="Ana",
        email=f"ana-{uuid4()}@example.com",
        senha="segredo123",
        criado_em=_AGORA,
    )
    SqlAlchemyUsuarioRepository(session).salvar(usuario)
    return usuario


def _token(usuario_id, familia_id, token_hash: str) -> RefreshToken:
    return RefreshToken(
        id=uuid4(),
        usuario_id=usuario_id,
        token_hash=token_hash,
        familia_id=familia_id,
        criado_em=_AGORA,
        expira_em=_AGORA + timedelta(days=30),
    )


def test_salvar_e_buscar_por_hash_devolve_datas_com_fuso(session):
    usuario = _novo_usuario(session)
    repositorio = SqlAlchemyRefreshTokenRepository(session)
    token = _token(usuario.id, uuid4(), "a" * 64)

    repositorio.salvar(token)
    encontrado = repositorio.buscar_por_hash("a" * 64)

    assert encontrado == token
    assert encontrado.expira_em.tzinfo is not None
    assert encontrado.esta_expirado(_AGORA) is False


def test_buscar_por_hash_inexistente_devolve_none(session):
    assert SqlAlchemyRefreshTokenRepository(session).buscar_por_hash("b" * 64) is None


def test_salvar_atualiza_a_revogacao(session):
    usuario = _novo_usuario(session)
    repositorio = SqlAlchemyRefreshTokenRepository(session)
    token = _token(usuario.id, uuid4(), "c" * 64)
    repositorio.salvar(token)

    token.revogar(_AGORA)
    repositorio.salvar(token)

    assert repositorio.buscar_por_hash("c" * 64).revogado_em == _AGORA


def test_revogar_familia_so_afeta_a_familia_informada(session):
    usuario = _novo_usuario(session)
    repositorio = SqlAlchemyRefreshTokenRepository(session)
    familia = uuid4()
    outra = uuid4()
    repositorio.salvar(_token(usuario.id, familia, "d" * 64))
    repositorio.salvar(_token(usuario.id, familia, "e" * 64))
    repositorio.salvar(_token(usuario.id, outra, "f" * 64))

    repositorio.revogar_familia(familia, _AGORA)

    assert repositorio.buscar_por_hash("d" * 64).esta_revogado() is True
    assert repositorio.buscar_por_hash("e" * 64).esta_revogado() is True
    assert repositorio.buscar_por_hash("f" * 64).esta_revogado() is False


def test_hash_duplicado_viola_restricao_unica(session):
    usuario = _novo_usuario(session)
    repositorio = SqlAlchemyRefreshTokenRepository(session)
    repositorio.salvar(_token(usuario.id, uuid4(), "9" * 64))

    with pytest.raises(IntegrityError):
        repositorio.salvar(_token(usuario.id, uuid4(), "9" * 64))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker run -d --rm --name pg-refresh -e POSTGRES_USER=insightflow -e POSTGRES_PASSWORD=insightflow -e POSTGRES_DB=insightflow_test -p 5434:5432 postgres:16` (aguarde ~3s) e depois `TEST_DATABASE_URL=postgresql://insightflow:insightflow@localhost:5434/insightflow_test .venv/bin/pytest tests/integration/repositories/test_refresh_token_repository.py -q`
Expected: `ModuleNotFoundError: No module named 'app.repositories.sqlalchemy.refresh_token_repository'`.

- [ ] **Step 3: Write minimal implementation**

`src/app/db/models/refresh_token.py`:

```python
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RefreshTokenModel(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    usuario_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    familia_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revogado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

`src/app/repositories/sqlalchemy/refresh_token_repository.py`:

```python
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models.refresh_token import RefreshTokenModel
from app.domain.entities.refresh_token import RefreshToken
from app.repositories.interfaces.refresh_token_repository import RefreshTokenRepository


class SqlAlchemyRefreshTokenRepository(RefreshTokenRepository):
    def __init__(self, session: Session):
        self._session = session

    def salvar(self, token: RefreshToken) -> None:
        modelo = self._session.get(RefreshTokenModel, token.id)
        if modelo is None:
            modelo = RefreshTokenModel(id=token.id)
            self._session.add(modelo)
        modelo.usuario_id = token.usuario_id
        modelo.token_hash = token.token_hash
        modelo.familia_id = token.familia_id
        modelo.criado_em = token.criado_em
        modelo.expira_em = token.expira_em
        modelo.revogado_em = token.revogado_em
        self._session.commit()

    def buscar_por_hash(self, token_hash: str) -> RefreshToken | None:
        modelo = self._session.scalars(
            select(RefreshTokenModel).where(RefreshTokenModel.token_hash == token_hash)
        ).first()
        return self._para_entidade(modelo) if modelo is not None else None

    def revogar_familia(self, familia_id: UUID, revogado_em: datetime) -> None:
        self._session.execute(
            update(RefreshTokenModel)
            .where(
                RefreshTokenModel.familia_id == familia_id,
                RefreshTokenModel.revogado_em.is_(None),
            )
            .values(revogado_em=revogado_em)
        )
        self._session.commit()

    @staticmethod
    def _para_entidade(modelo: RefreshTokenModel) -> RefreshToken:
        return RefreshToken(
            id=modelo.id,
            usuario_id=modelo.usuario_id,
            token_hash=modelo.token_hash,
            familia_id=modelo.familia_id,
            criado_em=modelo.criado_em,
            expira_em=modelo.expira_em,
            revogado_em=modelo.revogado_em,
        )
```

`alembic/versions/f1a7c3e9b2d4_cria_tabela_refresh_tokens.py`:

```python
"""cria tabela refresh_tokens

Revision ID: f1a7c3e9b2d4
Revises: c9e3a5b7d1f2
Create Date: 2026-10-04 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f1a7c3e9b2d4"
down_revision: str | Sequence[str] | None = "c9e3a5b7d1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("usuario_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("familia_id", sa.Uuid(), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expira_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revogado_em", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_refresh_tokens_familia_id", "refresh_tokens", ["familia_id"])


def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_familia_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
```

Em `alembic/env.py` e em `tests/integration/conftest.py`, adicione `from app.db.models.refresh_token import RefreshTokenModel` junto dos outros imports de models (ordem alfabética, antes de `sinal`). Se o `ruff` acusar o import como não usado (`F401`), siga o tratamento já usado para os outros models nesses arquivos.

- [ ] **Step 4: Run tests to verify they pass**

Run: `TEST_DATABASE_URL=postgresql://insightflow:insightflow@localhost:5434/insightflow_test .venv/bin/pytest tests/integration/repositories/test_refresh_token_repository.py -q && .venv/bin/pytest tests/unit -q && .venv/bin/ruff check src tests alembic`
Expected: 5 testes de integração passam; unitários passam; ruff limpo.

- [ ] **Step 5: Verify the migration**

Run (contra um banco limpo no mesmo container):

```bash
docker exec pg-refresh psql -U insightflow -c "CREATE DATABASE insightflow_migracao"
DATABASE_URL=postgresql://insightflow:insightflow@localhost:5434/insightflow_migracao .venv/bin/alembic upgrade head
docker exec pg-refresh psql -U insightflow -d insightflow_migracao -c "\d refresh_tokens"
DATABASE_URL=postgresql://insightflow:insightflow@localhost:5434/insightflow_migracao .venv/bin/alembic downgrade -1
docker exec pg-refresh psql -U insightflow -d insightflow_migracao -c "\dt refresh_tokens"
```

Expected: `upgrade` termina em `f1a7c3e9b2d4`; `\d` mostra as 7 colunas, a FK com `ON DELETE CASCADE`, o unique em `token_hash` e o índice em `familia_id`; depois do `downgrade`, `Did not find any relation named "refresh_tokens"`.

- [ ] **Step 6: Commit**

```bash
git add src/app/db/models/refresh_token.py src/app/repositories/sqlalchemy/refresh_token_repository.py alembic/versions/f1a7c3e9b2d4_cria_tabela_refresh_tokens.py alembic/env.py tests/integration/conftest.py tests/integration/repositories/test_refresh_token_repository.py
```

Mensagem: `feat(auth): persiste refresh tokens (tabela refresh_tokens)`

---

### Task 4: API — emissão no cadastro/login, `/auth/refresh` e `/auth/logout`

**Files:**
- Modify: `src/app/core/config.py` (`jwt_expiration_minutes = 30`, `refresh_token_expiracao_dias = 30`)
- Modify: `.env.example` (`JWT_EXPIRATION_MINUTES=30`, `REFRESH_TOKEN_EXPIRACAO_DIAS=30`)
- Modify: `src/app/api/v1/schemas/token.py`, `src/app/api/v1/schemas/auth.py`
- Modify: `src/app/api/deps.py`
- Modify: `src/app/api/v1/controllers/auth.py`, `src/app/api/v1/controllers/usuarios.py`
- Modify: `tests/unit/api/conftest.py`
- Test: `tests/unit/api/test_auth_controller.py`, `tests/unit/core/test_config.py`

**Interfaces:**
- Consumes: `RefreshTokenService`, `ParTokens` (Task 2); `SqlAlchemyRefreshTokenRepository` (Task 3); `FakeRefreshTokenRepository` (Task 1).
- Produces: `TokenResponse(access_token, refresh_token, token_type="bearer", expires_in)` com `TokenResponse.de(par: ParTokens)`; `RefreshRequest(refresh_token: str)`; `get_refresh_token_repository(session)`, `get_refresh_token_service(...)`; fixture `refresh_token_repository` no conftest da API.

- [ ] **Step 1: Write the failing tests**

Em `tests/unit/core/test_config.py`:

```python
def test_validades_padrao_do_access_e_do_refresh_token():
    settings = Settings(_env_file=None)

    assert settings.jwt_expiration_minutes == 30
    assert settings.refresh_token_expiracao_dias == 30
```

Ao fim de `tests/unit/api/test_auth_controller.py`:

```python
def _cadastrar(client) -> dict:
    resposta = client.post(
        "/api/v1/usuarios",
        json={"nome": "Ana", "email": "ana@example.com", "senha": "segredo123"},
    )
    return resposta.json()


def test_cadastro_e_login_devolvem_refresh_token_e_expires_in(client):
    cadastro = _cadastrar(client)
    login = client.post(
        "/api/v1/auth/login", json={"email": "ana@example.com", "senha": "segredo123"}
    ).json()

    for corpo in (cadastro, login):
        assert corpo["refresh_token"]
        assert corpo["expires_in"] == 1800
        assert corpo["token_type"] == "bearer"
    assert cadastro["refresh_token"] != login["refresh_token"]


def test_refresh_devolve_tokens_novos_que_autenticam(client):
    tokens = _cadastrar(client)

    resposta = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})

    assert resposta.status_code == 200
    novos = resposta.json()
    assert novos["refresh_token"] != tokens["refresh_token"]
    protegido = client.get(
        "/api/v1/watchlist", headers={"Authorization": f"Bearer {novos['access_token']}"}
    )
    assert protegido.status_code == 200


def test_reuso_do_refresh_antigo_retorna_401_e_derruba_o_novo(client):
    tokens = _cadastrar(client)
    novos = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    ).json()

    reuso = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    depois = client.post("/api/v1/auth/refresh", json={"refresh_token": novos["refresh_token"]})

    assert reuso.status_code == 401
    assert depois.status_code == 401


def test_refresh_com_token_desconhecido_retorna_401(client):
    resposta = client.post("/api/v1/auth/refresh", json={"refresh_token": "nao-existe"})

    assert resposta.status_code == 401


def test_refresh_sem_corpo_retorna_422(client):
    assert client.post("/api/v1/auth/refresh", json={}).status_code == 422


def test_logout_retorna_204_e_o_refresh_seguinte_falha(client):
    tokens = _cadastrar(client)

    logout = client.post("/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    depois = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})

    assert logout.status_code == 204
    assert depois.status_code == 401


def test_logout_com_token_desconhecido_retorna_204(client):
    resposta = client.post("/api/v1/auth/logout", json={"refresh_token": "nao-existe"})

    assert resposta.status_code == 204
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/api/test_auth_controller.py tests/unit/core/test_config.py -q`
Expected: os testes novos falham (`KeyError: 'refresh_token'`, 404 em `/auth/refresh` e `/auth/logout`, `jwt_expiration_minutes == 1440`).

- [ ] **Step 3: Write minimal implementation**

`src/app/core/config.py`: troque `jwt_expiration_minutes: int = 1440` por `jwt_expiration_minutes: int = 30` e adicione logo abaixo `refresh_token_expiracao_dias: int = 30`. Em `.env.example`, troque `JWT_EXPIRATION_MINUTES=1440` por `JWT_EXPIRATION_MINUTES=30` e adicione abaixo `REFRESH_TOKEN_EXPIRACAO_DIAS=30`.

`src/app/api/v1/schemas/token.py`:

```python
from pydantic import BaseModel

from app.services.refresh_token_service import ParTokens


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

    @staticmethod
    def de(par: ParTokens) -> "TokenResponse":
        return TokenResponse(
            access_token=par.access_token,
            refresh_token=par.refresh_token,
            expires_in=par.expires_in,
        )
```

Em `src/app/api/v1/schemas/auth.py`, adicione:

```python
class RefreshRequest(BaseModel):
    refresh_token: str
```

`src/app/api/deps.py` — junto dos outros `get_*_repository`:

```python
def get_refresh_token_repository(
    session: Session = Depends(get_db_session),
) -> RefreshTokenRepository:
    return SqlAlchemyRefreshTokenRepository(session)


def get_refresh_token_service(
    refresh_token_repository: RefreshTokenRepository = Depends(get_refresh_token_repository),
    usuario_repository: UsuarioRepository = Depends(get_usuario_repository),
    settings: Settings = Depends(get_settings),
) -> RefreshTokenService:
    return RefreshTokenService(
        refresh_token_repository,
        usuario_repository,
        jwt_secret_key=settings.jwt_secret_key,
        access_expiracao_minutos=settings.jwt_expiration_minutes,
        refresh_expiracao_dias=settings.refresh_token_expiracao_dias,
    )
```

(importe `RefreshTokenRepository`, `SqlAlchemyRefreshTokenRepository` e `RefreshTokenService`; `get_refresh_token_service` precisa ficar depois de `get_usuario_repository`).

`src/app/api/v1/controllers/auth.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_refresh_token_service, get_usuario_service
from app.api.v1.schemas.auth import LoginRequest, RefreshRequest
from app.api.v1.schemas.token import TokenResponse
from app.services.exceptions import CredenciaisInvalidasError, RefreshTokenInvalidoError
from app.services.refresh_token_service import RefreshTokenService
from app.services.usuario_service import UsuarioService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(
    dados: LoginRequest,
    service: UsuarioService = Depends(get_usuario_service),
    tokens: RefreshTokenService = Depends(get_refresh_token_service),
) -> TokenResponse:
    try:
        usuario = service.autenticar(email=dados.email, senha=dados.senha)
    except CredenciaisInvalidasError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciais inválidas") from exc

    return TokenResponse.de(tokens.emitir(usuario.id))


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    dados: RefreshRequest,
    tokens: RefreshTokenService = Depends(get_refresh_token_service),
) -> TokenResponse:
    try:
        par = tokens.renovar(dados.refresh_token)
    except RefreshTokenInvalidoError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token invalido") from exc

    return TokenResponse.de(par)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    dados: RefreshRequest,
    tokens: RefreshTokenService = Depends(get_refresh_token_service),
) -> None:
    tokens.revogar(dados.refresh_token)
```

`src/app/api/v1/controllers/usuarios.py` — troque a dependência `settings: Settings = Depends(get_settings)` por `tokens: RefreshTokenService = Depends(get_refresh_token_service)` e as duas últimas linhas por `return TokenResponse.de(tokens.emitir(usuario.id))`; remova os imports que ficarem sem uso (`criar_token`, `Settings`, `get_settings`).

`tests/unit/api/conftest.py`:
- fixture nova:

```python
@pytest.fixture
def refresh_token_repository() -> FakeRefreshTokenRepository:
    return FakeRefreshTokenRepository()
```

- adicione `refresh_token_repository: FakeRefreshTokenRepository` aos parâmetros da fixture `client` e o override `app.dependency_overrides[get_refresh_token_repository] = lambda: refresh_token_repository`, com os imports correspondentes.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit tests/test_health.py -q && .venv/bin/ruff check src tests`
Expected: todos passam.

- [ ] **Step 5: Commit**

```bash
git add src/app/core/config.py .env.example src/app/api tests/unit/api tests/unit/core/test_config.py
```

Mensagem: `feat(auth): adiciona /auth/refresh e /auth/logout e emite refresh token no login`
