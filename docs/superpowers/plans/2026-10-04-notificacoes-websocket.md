# Notificações em tempo real (WebSocket) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar cada notificação nova, em tempo real, a todos os sockets abertos do dono por `WS /api/v1/notificacoes/ws`, com fan-out por Redis pub/sub e um ponto de extensão (`CanalNotificacao`) para os futuros canais Expo e Web Push.

**Architecture:** `NotificacaoService` grava a notificação e chama cada `CanalNotificacao`; o `CanalTempoReal` publica no `BarramentoNotificacoes` (Redis em produção, fake em memória nos testes). O endpoint WebSocket autentica pela primeira mensagem, assina o barramento do usuário e repassa as mensagens, com ping periódico, reautenticação e fechamento 4401.

**Tech Stack:** FastAPI 0.141 / Starlette 1.6 (WebSocket), redis-py 8.1 (`redis` e `redis.asyncio`), python-jose, pydantic-core, pytest.

**Spec:** `docs/superpowers/specs/2026-10-04-notificacoes-websocket-design.md`

## Global Constraints

- Zero comentários no código e nos testes. Nomes em português, sem acentos em identificadores.
- Usar `.venv/bin/pytest`, `.venv/bin/ruff`. Formatar só os arquivos tocados.
- Protocolo exatamente como na spec: mensagens `autenticar`, `autenticado`, `notificacao`, `ping`; fechamento com código `4401`.
- Canal Redis: `notificacoes:{usuario_id}`.
- Config: `ws_timeout_autenticacao_segundos: float = 10`, `ws_intervalo_ping_segundos: float = 30`.
- Falha de canal nunca interrompe a gravação nem os outros canais (`logger.warning(..., exc_info=True)`).
- O usuário comita pessoalmente: nos passos de commit, apenas `git add` e a mensagem proposta (Português, Conventional Commits com escopo, terminando com `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`).
- Redis descartável para integração e verificação real: `docker run -d --rm --name redis-ws -p 6382:6379 redis:7` e `TEST_REDIS_URL=redis://localhost:6382/1`.

**Desvio deliberado da spec:** o teste de "fluxo completo" usa `NotificacaoService.enviar_alerta_personalizado` com o canal real e o barramento fake (service → canal → barramento → socket), em vez de rodar o ciclo de monitoramento inteiro dentro do teste da API. O ciclo já tem testes próprios que garantem que ele chama `enviar_alerta_personalizado`.

**Decisão de implementação:** o WebSocket não recebe o `UsuarioRepository` da requisição (a sessão SQLAlchemy ficaria aberta, com transação, enquanto o socket durar). Ele recebe um `buscar_usuario: Callable[[UUID], Usuario | None]` que abre e fecha uma sessão por consulta, executado com `asyncio.to_thread`.

## Review Focus

1. **Notificação publicada logo depois do `autenticado`** — a assinatura precisa existir antes de o servidor responder `autenticado`; senão a primeira notificação se perde. Teste na Task 4.
2. **Reautenticação com token de outro usuário** — deve fechar 4401, não trocar silenciosamente o dono do socket. Teste na Task 4.
3. **Primeira mensagem que não é JSON** — deve fechar 4401, não derrubar o servidor com exceção. Teste na Task 4.
4. **Redis fora do ar na publicação** — o ciclo do scheduler e a requisição continuam; a notificação fica gravada. Teste na Task 2.
5. **Desconexão do cliente** — a assinatura do barramento é fechada (sem vazamento de assinantes). Teste na Task 4.

---

## File Structure

| Arquivo | Responsabilidade |
|---|---|
| `src/app/notifications/serializacao.py` (novo) | `notificacao_para_dict` |
| `src/app/core/security.py` | `decodificar_token_com_expiracao` |
| `src/app/notifications/barramento.py` (novo) | ABCs `Assinatura` e `BarramentoNotificacoes` |
| `src/app/notifications/canal.py` (novo) | ABC `CanalNotificacao`, `CanalTempoReal` |
| `src/app/notifications/redis_barramento.py` (novo) | `RedisBarramentoNotificacoes` |
| `src/app/notifications/websocket.py` (novo) | `atender_conexao` |
| `src/app/services/notificacao_service.py` | Recebe `canais` |
| `src/app/api/v1/controllers/notificacoes.py` | Rota WebSocket |
| `src/app/api/deps.py`, `src/app/scheduler/jobs.py` | Montagem |
| `src/app/core/config.py`, `.env.example` | Prazos do WebSocket |
| `tests/fixtures/fake_barramento_notificacoes.py` (novo) | Fake thread-safe |

---

### Task 1: Serialização e expiração do token

**Files:**
- Create: `src/app/notifications/serializacao.py`
- Modify: `src/app/core/security.py`
- Test: `tests/unit/notifications/__init__.py` (vazio), `tests/unit/notifications/test_serializacao.py`, `tests/unit/core/test_security.py`

**Interfaces:**
- Produces: `notificacao_para_dict(notificacao: Notificacao) -> dict`; `decodificar_token_com_expiracao(token: str, secret_key: str) -> tuple[UUID, datetime]` (lança `TokenInvalidoError`).

- [ ] **Step 1: Write the failing tests**

`tests/unit/notifications/test_serializacao.py`:

```python
from datetime import UTC, datetime
from uuid import uuid4

from app.api.v1.schemas.notificacao import NotificacaoResponse
from app.domain.entities.notificacao import Notificacao
from app.domain.enums.tipo_notificacao import TipoNotificacao
from app.notifications.serializacao import notificacao_para_dict


def _notificacao(ativo_id) -> Notificacao:
    return Notificacao(
        id=uuid4(),
        usuario_id=uuid4(),
        ativo_id=ativo_id,
        tipo=TipoNotificacao.ALERTA_DISPARADO,
        mensagem="PETR4 atingiu o alvo",
        contexto={"alerta_id": "x", "preco": "40.00"},
        criado_em=datetime(2026, 10, 4, 12, 0, tzinfo=UTC),
    )


def test_serializacao_igual_ao_json_do_endpoint_rest():
    notificacao = _notificacao(uuid4())

    assert notificacao_para_dict(notificacao) == NotificacaoResponse.de(notificacao).model_dump(
        mode="json"
    )


def test_serializacao_sem_ativo_igual_ao_json_do_endpoint_rest():
    notificacao = _notificacao(None)

    assert notificacao_para_dict(notificacao) == NotificacaoResponse.de(notificacao).model_dump(
        mode="json"
    )
```

Ao fim de `tests/unit/core/test_security.py` (reaproveite os imports já existentes no arquivo; adicione os que faltarem):

```python
def test_decodificar_token_com_expiracao_devolve_usuario_e_exp():
    usuario_id = uuid4()
    antes = datetime.now(UTC).replace(microsecond=0)

    token = criar_token(usuario_id, "segredo", expiracao_minutos=30)
    decodificado, expira_em = decodificar_token_com_expiracao(token, "segredo")

    assert decodificado == usuario_id
    assert expira_em.tzinfo is not None
    assert antes + timedelta(minutes=29) < expira_em <= antes + timedelta(minutes=31)


def test_decodificar_token_com_expiracao_com_segredo_errado_lanca_erro():
    token = criar_token(uuid4(), "segredo", expiracao_minutos=30)

    with pytest.raises(TokenInvalidoError):
        decodificar_token_com_expiracao(token, "outro")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/notifications tests/unit/core/test_security.py -q`
Expected: `ModuleNotFoundError: No module named 'app.notifications.serializacao'` e `ImportError` de `decodificar_token_com_expiracao`.

- [ ] **Step 3: Write minimal implementation**

`src/app/notifications/serializacao.py`:

```python
from __future__ import annotations

from pydantic_core import to_jsonable_python

from app.domain.entities.notificacao import Notificacao


def notificacao_para_dict(notificacao: Notificacao) -> dict:
    return to_jsonable_python(
        {
            "id": notificacao.id,
            "ativo_id": notificacao.ativo_id,
            "tipo": notificacao.tipo,
            "mensagem": notificacao.mensagem,
            "contexto": notificacao.contexto,
            "lida": notificacao.lida,
            "criado_em": notificacao.criado_em,
        }
    )
```

Em `src/app/core/security.py`, adicione:

```python
def decodificar_token_com_expiracao(token: str, secret_key: str) -> tuple[UUID, datetime]:
    try:
        payload = jwt.decode(token, secret_key, algorithms=[_ALGORITHM])
        return UUID(payload["sub"]), datetime.fromtimestamp(payload["exp"], tz=UTC)
    except (JWTError, KeyError, ValueError, TypeError) as exc:
        raise TokenInvalidoError from exc
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit -q && .venv/bin/ruff check src tests`
Expected: todos passam.

- [ ] **Step 5: Commit**

```bash
git add src/app/notifications/serializacao.py src/app/core/security.py tests/unit/notifications tests/unit/core/test_security.py
```

Mensagem: `feat(notificacoes): serializacao compartilhada e leitura do exp do token`

---

### Task 2: Barramento, canal e NotificacaoService com canais

**Files:**
- Create: `src/app/notifications/barramento.py`
- Create: `src/app/notifications/canal.py`
- Create: `tests/fixtures/fake_barramento_notificacoes.py`
- Modify: `src/app/services/notificacao_service.py`
- Test: `tests/unit/notifications/test_canal.py`, `tests/unit/services/test_notificacao_service.py`

**Interfaces:**
- Consumes: `notificacao_para_dict` (Task 1).
- Produces:
  - `Assinatura(ABC)`: `async def proxima(self) -> dict`, `async def fechar(self) -> None`.
  - `BarramentoNotificacoes(ABC)`: `def publicar(self, usuario_id: UUID, payload: dict) -> None`, `async def assinar(self, usuario_id: UUID) -> Assinatura` (a assinatura já está ativa quando o `await` retorna).
  - `CanalNotificacao(ABC)`: `def entregar(self, notificacao: Notificacao) -> None`; `CanalTempoReal(barramento)`.
  - `NotificacaoService(notificacao_repository, canais: Sequence[CanalNotificacao] = ())`.
  - `FakeBarramentoNotificacoes` com `publicados: list[tuple[UUID, dict]]`, `total_assinantes(usuario_id) -> int`, `falhar: bool` (quando `True`, `publicar` lança `ConnectionError`).

- [ ] **Step 1: Write the fake and the failing tests**

`tests/fixtures/fake_barramento_notificacoes.py`:

```python
from __future__ import annotations

import asyncio
import threading
from uuid import UUID

from app.notifications.barramento import Assinatura, BarramentoNotificacoes


class _AssinaturaFake(Assinatura):
    def __init__(self, barramento: FakeBarramentoNotificacoes, usuario_id: UUID):
        self._barramento = barramento
        self._usuario_id = usuario_id
        self._loop = asyncio.get_running_loop()
        self._fila: asyncio.Queue = asyncio.Queue()

    def _receber(self, payload: dict) -> None:
        self._loop.call_soon_threadsafe(self._fila.put_nowait, payload)

    async def proxima(self) -> dict:
        return await self._fila.get()

    async def fechar(self) -> None:
        self._barramento._remover(self._usuario_id, self)


class FakeBarramentoNotificacoes(BarramentoNotificacoes):
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._assinaturas: dict[UUID, list[_AssinaturaFake]] = {}
        self.publicados: list[tuple[UUID, dict]] = []
        self.falhar = False

    def publicar(self, usuario_id: UUID, payload: dict) -> None:
        if self.falhar:
            raise ConnectionError("barramento fora do ar")
        self.publicados.append((usuario_id, payload))
        with self._lock:
            alvos = list(self._assinaturas.get(usuario_id, []))
        for assinatura in alvos:
            assinatura._receber(payload)

    async def assinar(self, usuario_id: UUID) -> Assinatura:
        assinatura = _AssinaturaFake(self, usuario_id)
        with self._lock:
            self._assinaturas.setdefault(usuario_id, []).append(assinatura)
        return assinatura

    def total_assinantes(self, usuario_id: UUID) -> int:
        with self._lock:
            return len(self._assinaturas.get(usuario_id, []))

    def _remover(self, usuario_id: UUID, assinatura: _AssinaturaFake) -> None:
        with self._lock:
            if assinatura in self._assinaturas.get(usuario_id, []):
                self._assinaturas[usuario_id].remove(assinatura)
```

`tests/unit/notifications/test_canal.py`:

```python
from datetime import UTC, datetime
from uuid import uuid4

from app.domain.entities.notificacao import Notificacao
from app.domain.enums.tipo_notificacao import TipoNotificacao
from app.notifications.canal import CanalTempoReal
from app.notifications.serializacao import notificacao_para_dict
from tests.fixtures.fake_barramento_notificacoes import FakeBarramentoNotificacoes


def test_canal_tempo_real_publica_no_canal_do_dono():
    barramento = FakeBarramentoNotificacoes()
    notificacao = Notificacao(
        id=uuid4(),
        usuario_id=uuid4(),
        ativo_id=None,
        tipo=TipoNotificacao.RESUMO_DIARIO,
        mensagem="Resumo diario da carteira",
        contexto={"texto": "ok"},
        criado_em=datetime(2026, 10, 4, 12, 0, tzinfo=UTC),
    )

    CanalTempoReal(barramento).entregar(notificacao)

    assert barramento.publicados == [
        (
            notificacao.usuario_id,
            {"tipo": "notificacao", "notificacao": notificacao_para_dict(notificacao)},
        )
    ]
```

Em `tests/unit/services/test_notificacao_service.py`, adicione (reaproveite os helpers/fixtures que o arquivo já tem para montar `Sinal`, `Ativo`, `AlertaPersonalizado` e `CotacaoAtual`; se não houver, crie-os no próprio teste com os mesmos campos usados pelos testes existentes do arquivo):

```python
class _CanalQueFalha(CanalNotificacao):
    def entregar(self, notificacao) -> None:
        raise RuntimeError("canal fora do ar")


class _CanalQueRegistra(CanalNotificacao):
    def __init__(self) -> None:
        self.entregues = []

    def entregar(self, notificacao) -> None:
        self.entregues.append(notificacao)


def test_cada_envio_entrega_a_notificacao_gravada_em_todos_os_canais():
    repositorio = FakeNotificacaoRepository()
    primeiro = _CanalQueRegistra()
    segundo = _CanalQueRegistra()
    service = NotificacaoService(repositorio, canais=[primeiro, segundo])
    usuario_id = uuid4()

    resumo = service.enviar_resumo_diario(usuario_id, "Texto do resumo", {})

    assert primeiro.entregues == [resumo]
    assert segundo.entregues == [resumo]
    assert repositorio.buscar_por_id(resumo.id) == resumo


def test_falha_de_um_canal_nao_impede_gravacao_nem_os_demais_canais():
    repositorio = FakeNotificacaoRepository()
    registrador = _CanalQueRegistra()
    service = NotificacaoService(repositorio, canais=[_CanalQueFalha(), registrador])

    resumo = service.enviar_resumo_diario(uuid4(), "Texto do resumo", {})

    assert repositorio.buscar_por_id(resumo.id) == resumo
    assert registrador.entregues == [resumo]


def test_barramento_fora_do_ar_nao_impede_a_gravacao():
    repositorio = FakeNotificacaoRepository()
    barramento = FakeBarramentoNotificacoes()
    barramento.falhar = True
    service = NotificacaoService(repositorio, canais=[CanalTempoReal(barramento)])

    resumo = service.enviar_resumo_diario(uuid4(), "Texto do resumo", {})

    assert repositorio.buscar_por_id(resumo.id) == resumo


def test_marcar_como_lida_nao_entrega_nos_canais():
    repositorio = FakeNotificacaoRepository()
    registrador = _CanalQueRegistra()
    service = NotificacaoService(repositorio, canais=[registrador])
    usuario_id = uuid4()
    resumo = service.enviar_resumo_diario(usuario_id, "Texto do resumo", {})
    registrador.entregues.clear()

    service.marcar_como_lida(usuario_id, resumo.id)

    assert registrador.entregues == []
```

Adicione também um teste para `enviar_alerta` e outro para `enviar_alerta_personalizado` que verificam `registrador.entregues == [notificacao_devolvida]`, montando os argumentos do mesmo jeito que os testes existentes desses métodos no arquivo.

Imports necessários no topo do arquivo de teste: `from app.notifications.canal import CanalNotificacao, CanalTempoReal` e `from tests.fixtures.fake_barramento_notificacoes import FakeBarramentoNotificacoes`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/notifications tests/unit/services/test_notificacao_service.py -q`
Expected: `ModuleNotFoundError: No module named 'app.notifications.barramento'`.

- [ ] **Step 3: Write minimal implementation**

`src/app/notifications/barramento.py`:

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID


class Assinatura(ABC):
    @abstractmethod
    async def proxima(self) -> dict: ...

    @abstractmethod
    async def fechar(self) -> None: ...


class BarramentoNotificacoes(ABC):
    @abstractmethod
    def publicar(self, usuario_id: UUID, payload: dict) -> None: ...

    @abstractmethod
    async def assinar(self, usuario_id: UUID) -> Assinatura: ...
```

`src/app/notifications/canal.py`:

```python
from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities.notificacao import Notificacao
from app.notifications.barramento import BarramentoNotificacoes
from app.notifications.serializacao import notificacao_para_dict


class CanalNotificacao(ABC):
    @abstractmethod
    def entregar(self, notificacao: Notificacao) -> None: ...


class CanalTempoReal(CanalNotificacao):
    def __init__(self, barramento: BarramentoNotificacoes):
        self._barramento = barramento

    def entregar(self, notificacao: Notificacao) -> None:
        self._barramento.publicar(
            notificacao.usuario_id,
            {"tipo": "notificacao", "notificacao": notificacao_para_dict(notificacao)},
        )
```

`src/app/services/notificacao_service.py`:
- imports: `import logging`, `from collections.abc import Sequence`, `from app.notifications.canal import CanalNotificacao`; `logger = logging.getLogger(__name__)`.
- construtor:

```python
    def __init__(
        self,
        notificacao_repository: NotificacaoRepository,
        canais: Sequence[CanalNotificacao] = (),
    ):
        self._notificacao_repository = notificacao_repository
        self._canais = list(canais)
```

- novo método privado:

```python
    def _distribuir(self, notificacao: Notificacao) -> None:
        for canal in self._canais:
            try:
                canal.entregar(notificacao)
            except Exception:
                logger.warning(
                    "Falha ao entregar a notificacao %s pelo canal %s.",
                    notificacao.id,
                    type(canal).__name__,
                    exc_info=True,
                )
```

- em `enviar_alerta`, `enviar_alerta_personalizado` e `enviar_resumo_diario`, logo depois de `self._notificacao_repository.salvar(notificacao)`, chame `self._distribuir(notificacao)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit -q && .venv/bin/ruff check src tests`
Expected: todos passam (os testes existentes do service e do ciclo continuam passando, porque `canais` tem padrão vazio).

- [ ] **Step 5: Commit**

```bash
git add src/app/notifications/barramento.py src/app/notifications/canal.py src/app/services/notificacao_service.py tests/fixtures/fake_barramento_notificacoes.py tests/unit/notifications/test_canal.py tests/unit/services/test_notificacao_service.py
```

Mensagem: `feat(notificacoes): adiciona canais de entrega e barramento de notificacoes`

---

### Task 3: Barramento Redis

**Files:**
- Create: `src/app/notifications/redis_barramento.py`
- Test: `tests/integration/notifications/__init__.py` (vazio), `tests/integration/notifications/test_redis_barramento.py`

**Interfaces:**
- Consumes: `Assinatura`, `BarramentoNotificacoes` (Task 2).
- Produces: `RedisBarramentoNotificacoes(redis_sync: redis.Redis, redis_async: redis.asyncio.Redis)`.

- [ ] **Step 1: Write the failing tests**

`tests/integration/notifications/test_redis_barramento.py`:

```python
import asyncio
import os
from uuid import uuid4

import pytest
import redis
import redis.asyncio

from app.notifications.redis_barramento import RedisBarramentoNotificacoes

pytestmark = pytest.mark.integration

TEST_REDIS_URL = os.getenv("TEST_REDIS_URL", "redis://localhost:6381/1")


def _barramento() -> RedisBarramentoNotificacoes:
    return RedisBarramentoNotificacoes(
        redis.Redis.from_url(TEST_REDIS_URL), redis.asyncio.Redis.from_url(TEST_REDIS_URL)
    )


def test_publicar_entrega_o_payload_a_quem_assinou_o_usuario():
    async def cenario():
        barramento = _barramento()
        usuario_id = uuid4()
        assinatura = await barramento.assinar(usuario_id)
        await asyncio.to_thread(barramento.publicar, usuario_id, {"tipo": "notificacao", "n": 1})
        recebido = await asyncio.wait_for(assinatura.proxima(), timeout=2)
        await assinatura.fechar()
        return recebido

    assert asyncio.run(cenario()) == {"tipo": "notificacao", "n": 1}


def test_assinante_de_outro_usuario_nao_recebe():
    async def cenario():
        barramento = _barramento()
        assinatura = await barramento.assinar(uuid4())
        await asyncio.to_thread(barramento.publicar, uuid4(), {"tipo": "notificacao"})
        try:
            await asyncio.wait_for(assinatura.proxima(), timeout=0.5)
            return "recebeu"
        except TimeoutError:
            return "nada"
        finally:
            await assinatura.fechar()

    assert asyncio.run(cenario()) == "nada"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker run -d --rm --name redis-ws -p 6382:6379 redis:7` e `TEST_REDIS_URL=redis://localhost:6382/1 .venv/bin/pytest tests/integration/notifications -q`
Expected: `ModuleNotFoundError: No module named 'app.notifications.redis_barramento'`.

- [ ] **Step 3: Write minimal implementation**

`src/app/notifications/redis_barramento.py`:

```python
from __future__ import annotations

import json
from uuid import UUID

import redis
import redis.asyncio

from app.notifications.barramento import Assinatura, BarramentoNotificacoes


def _canal(usuario_id: UUID) -> str:
    return f"notificacoes:{usuario_id}"


class _AssinaturaRedis(Assinatura):
    def __init__(self, pubsub: redis.asyncio.client.PubSub):
        self._pubsub = pubsub

    async def proxima(self) -> dict:
        while True:
            mensagem = await self._pubsub.get_message(ignore_subscribe_messages=True, timeout=None)
            if mensagem is not None and mensagem.get("type") == "message":
                return json.loads(mensagem["data"])

    async def fechar(self) -> None:
        await self._pubsub.unsubscribe()
        await self._pubsub.aclose()


class RedisBarramentoNotificacoes(BarramentoNotificacoes):
    def __init__(self, redis_sync: redis.Redis, redis_async: redis.asyncio.Redis):
        self._redis_sync = redis_sync
        self._redis_async = redis_async

    def publicar(self, usuario_id: UUID, payload: dict) -> None:
        self._redis_sync.publish(_canal(usuario_id), json.dumps(payload))

    async def assinar(self, usuario_id: UUID) -> Assinatura:
        pubsub = self._redis_async.pubsub()
        await pubsub.subscribe(_canal(usuario_id))
        return _AssinaturaRedis(pubsub)
```

Se `get_message(timeout=None)` não bloquear nesta versão do redis-py (retornar `None` de imediato em loop), troque o laço por iteração em `self._pubsub.listen()` guardado como iterador no construtor da assinatura, e registre um `Ruling:` no ledger.

- [ ] **Step 4: Run tests to verify they pass**

Run: `TEST_REDIS_URL=redis://localhost:6382/1 .venv/bin/pytest tests/integration/notifications -q && .venv/bin/pytest tests/unit -q && .venv/bin/ruff check src tests`
Expected: 2 testes de integração passam; unitários passam.

- [ ] **Step 5: Commit**

```bash
git add src/app/notifications/redis_barramento.py tests/integration/notifications
```

Mensagem: `feat(notificacoes): adiciona barramento de notificacoes sobre Redis pub/sub`

---

### Task 4: Endpoint WebSocket

**Files:**
- Create: `src/app/notifications/websocket.py`
- Modify: `src/app/api/v1/controllers/notificacoes.py`
- Modify: `src/app/api/deps.py` (`get_barramento_notificacoes`, `get_buscador_usuario`)
- Modify: `src/app/core/config.py`, `.env.example`
- Test: `tests/unit/api/test_notificacoes_ws.py`

**Interfaces:**
- Consumes: `decodificar_token_com_expiracao`, `TokenInvalidoError` (Task 1); `BarramentoNotificacoes`, `CanalTempoReal`, `FakeBarramentoNotificacoes` (Task 2); `RedisBarramentoNotificacoes` (Task 3).
- Produces: `async def atender_conexao(websocket, buscar_usuario: Callable[[UUID], Usuario | None], barramento, jwt_secret_key: str, timeout_autenticacao: float, intervalo_ping: float) -> None`; `CODIGO_NAO_AUTENTICADO = 4401`; `get_barramento_notificacoes(settings) -> BarramentoNotificacoes`; `get_buscador_usuario(settings) -> Callable[[UUID], Usuario | None]`; `Settings.ws_timeout_autenticacao_segundos`, `Settings.ws_intervalo_ping_segundos`.

- [ ] **Step 1: Write the failing tests**

`tests/unit/api/test_notificacoes_ws.py`:

```python
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from starlette.websockets import WebSocketDisconnect

from app.api.deps import get_barramento_notificacoes, get_buscador_usuario
from app.core.config import Settings, get_settings
from app.core.security import criar_token
from app.domain.entities.alerta_personalizado import AlertaPersonalizado
from app.domain.entities.usuario import Usuario
from app.domain.enums.tipo_condicao_alerta import TipoCondicaoAlerta
from app.integrations.brapi.client import CotacaoAtual
from app.main import app
from app.notifications.canal import CanalTempoReal
from app.services.notificacao_service import NotificacaoService
from tests.fixtures.fake_barramento_notificacoes import FakeBarramentoNotificacoes
from tests.fixtures.fake_notificacao_repository import FakeNotificacaoRepository
from tests.fixtures.fake_usuario_repository import FakeUsuarioRepository

_SEGREDO = "segredo-ws"
_URL = "/api/v1/notificacoes/ws"


class _Ambiente:
    def __init__(self, timeout_autenticacao: float = 1.0, intervalo_ping: float = 60.0):
        self.usuarios = FakeUsuarioRepository()
        self.barramento = FakeBarramentoNotificacoes()
        settings = Settings(
            _env_file=None,
            jwt_secret_key=_SEGREDO,
            ws_timeout_autenticacao_segundos=timeout_autenticacao,
            ws_intervalo_ping_segundos=intervalo_ping,
        )
        app.dependency_overrides[get_settings] = lambda: settings
        app.dependency_overrides[get_barramento_notificacoes] = lambda: self.barramento
        app.dependency_overrides[get_buscador_usuario] = lambda: self.usuarios.buscar_por_id
        self.client = TestClient(app)

    def novo_usuario(self, ativo: bool = True) -> Usuario:
        usuario = Usuario.criar(
            id=uuid4(),
            nome="Ana",
            email=f"ana-{uuid4()}@example.com",
            senha="segredo123",
            criado_em=datetime.now(UTC),
        )
        usuario.ativo = ativo
        self.usuarios.salvar(usuario)
        return usuario


@pytest.fixture
def ambiente():
    yield _Ambiente()
    app.dependency_overrides.clear()


@pytest.fixture
def ambiente_rapido():
    yield _Ambiente(timeout_autenticacao=0.2, intervalo_ping=0.2)
    app.dependency_overrides.clear()


def _token(usuario: Usuario) -> str:
    return criar_token(usuario.id, _SEGREDO, expiracao_minutos=30)


def _autenticar(ws, token: str) -> dict:
    ws.send_json({"tipo": "autenticar", "token": token})
    return ws.receive_json()


def _espera_fechamento_4401(ws) -> None:
    with pytest.raises(WebSocketDisconnect) as erro:
        ws.receive_json()
    assert erro.value.code == 4401


def _publicar_para(ambiente: _Ambiente, usuario_id) -> None:
    ambiente.barramento.publicar(usuario_id, {"tipo": "notificacao", "notificacao": {"id": "x"}})


def test_token_valido_recebe_autenticado(ambiente):
    usuario = ambiente.novo_usuario()

    with ambiente.client.websocket_connect(_URL) as ws:
        assert _autenticar(ws, _token(usuario)) == {"tipo": "autenticado"}


def test_token_invalido_fecha_4401(ambiente):
    with ambiente.client.websocket_connect(_URL) as ws:
        ws.send_json({"tipo": "autenticar", "token": "lixo"})
        _espera_fechamento_4401(ws)


def test_usuario_inativo_fecha_4401(ambiente):
    usuario = ambiente.novo_usuario(ativo=False)

    with ambiente.client.websocket_connect(_URL) as ws:
        ws.send_json({"tipo": "autenticar", "token": _token(usuario)})
        _espera_fechamento_4401(ws)


def test_primeira_mensagem_que_nao_e_autenticar_fecha_4401(ambiente):
    with ambiente.client.websocket_connect(_URL) as ws:
        ws.send_json({"tipo": "outra"})
        _espera_fechamento_4401(ws)


def test_primeira_mensagem_que_nao_e_json_fecha_4401(ambiente):
    with ambiente.client.websocket_connect(_URL) as ws:
        ws.send_text("isto nao e json")
        _espera_fechamento_4401(ws)


def test_silencio_alem_do_prazo_fecha_4401(ambiente_rapido):
    with ambiente_rapido.client.websocket_connect(_URL) as ws:
        _espera_fechamento_4401(ws)


def test_notificacao_do_usuario_chega_e_a_de_outro_nao(ambiente):
    usuario = ambiente.novo_usuario()
    outro = ambiente.novo_usuario()

    with ambiente.client.websocket_connect(_URL) as ws:
        _autenticar(ws, _token(usuario))
        _publicar_para(ambiente, outro.id)
        ambiente.barramento.publicar(
            usuario.id, {"tipo": "notificacao", "notificacao": {"id": "meu"}}
        )

        assert ws.receive_json() == {"tipo": "notificacao", "notificacao": {"id": "meu"}}


def test_dois_sockets_do_mesmo_usuario_recebem_a_mesma_notificacao(ambiente):
    usuario = ambiente.novo_usuario()

    with ambiente.client.websocket_connect(_URL) as web, ambiente.client.websocket_connect(
        _URL
    ) as desktop:
        _autenticar(web, _token(usuario))
        _autenticar(desktop, _token(usuario))
        _publicar_para(ambiente, usuario.id)

        assert web.receive_json()["notificacao"] == {"id": "x"}
        assert desktop.receive_json()["notificacao"] == {"id": "x"}


def test_ping_chega_no_intervalo(ambiente_rapido):
    usuario = ambiente_rapido.novo_usuario()

    with ambiente_rapido.client.websocket_connect(_URL) as ws:
        _autenticar(ws, _token(usuario))

        assert ws.receive_json() == {"tipo": "ping"}


def test_reautenticacao_com_token_novo_mantem_a_conexao(ambiente):
    usuario = ambiente.novo_usuario()

    with ambiente.client.websocket_connect(_URL) as ws:
        _autenticar(ws, _token(usuario))

        assert _autenticar(ws, _token(usuario)) == {"tipo": "autenticado"}
        _publicar_para(ambiente, usuario.id)
        assert ws.receive_json()["tipo"] == "notificacao"


def test_reautenticacao_com_token_invalido_fecha_4401(ambiente):
    usuario = ambiente.novo_usuario()

    with ambiente.client.websocket_connect(_URL) as ws:
        _autenticar(ws, _token(usuario))
        ws.send_json({"tipo": "autenticar", "token": "lixo"})
        _espera_fechamento_4401(ws)


def test_reautenticacao_com_token_de_outro_usuario_fecha_4401(ambiente):
    usuario = ambiente.novo_usuario()
    outro = ambiente.novo_usuario()

    with ambiente.client.websocket_connect(_URL) as ws:
        _autenticar(ws, _token(usuario))
        ws.send_json({"tipo": "autenticar", "token": _token(outro)})
        _espera_fechamento_4401(ws)


def test_token_que_expira_sem_reautenticacao_fecha_4401(ambiente):
    usuario = ambiente.novo_usuario()
    token_curto = jwt.encode(
        {"sub": str(usuario.id), "exp": datetime.now(UTC) + timedelta(seconds=1)},
        _SEGREDO,
        algorithm="HS256",
    )

    with ambiente.client.websocket_connect(_URL) as ws:
        assert _autenticar(ws, token_curto) == {"tipo": "autenticado"}
        _espera_fechamento_4401(ws)


def test_desconexao_fecha_a_assinatura(ambiente):
    usuario = ambiente.novo_usuario()

    with ambiente.client.websocket_connect(_URL) as ws:
        _autenticar(ws, _token(usuario))
        assert ambiente.barramento.total_assinantes(usuario.id) == 1

    for _ in range(50):
        if ambiente.barramento.total_assinantes(usuario.id) == 0:
            break
        import time

        time.sleep(0.02)
    assert ambiente.barramento.total_assinantes(usuario.id) == 0


def test_alerta_disparado_pelo_service_chega_ao_socket_do_dono(ambiente):
    usuario = ambiente.novo_usuario()
    service = NotificacaoService(
        FakeNotificacaoRepository(), canais=[CanalTempoReal(ambiente.barramento)]
    )
    alerta = AlertaPersonalizado.criar(
        id=uuid4(),
        usuario_id=usuario.id,
        ativo_id=uuid4(),
        tipo_condicao=TipoCondicaoAlerta.PRECO_MAIOR_IGUAL,
        valor_alvo=Decimal("40.00"),
        moeda_alvo="BRL",
        criado_em=datetime.now(UTC),
    )
    cotacao = CotacaoAtual(
        ticker="PETR4",
        preco=Decimal("41.00"),
        variacao=Decimal(0),
        variacao_percentual=Decimal(0),
        maxima_dia=Decimal("41.00"),
        minima_dia=Decimal("41.00"),
        volume=Decimal(1),
    )

    with ambiente.client.websocket_connect(_URL) as ws:
        _autenticar(ws, _token(usuario))
        notificacao = service.enviar_alerta_personalizado(usuario.id, alerta, cotacao)

        mensagem = ws.receive_json()

    assert mensagem["tipo"] == "notificacao"
    assert mensagem["notificacao"]["id"] == str(notificacao.id)
    assert mensagem["notificacao"]["tipo"] == "ALERTA_DISPARADO"
    assert "PETR4" in mensagem["notificacao"]["mensagem"]
```

(Mova o `import time` do último teste de desconexão para o topo do arquivo antes de rodar o `ruff`; ele está inline aqui só para destacar.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/api/test_notificacoes_ws.py -q`
Expected: `ImportError: cannot import name 'get_barramento_notificacoes'`.

- [ ] **Step 3: Write minimal implementation**

`src/app/core/config.py` — junto das configs de cache, adicione:

```python
    ws_timeout_autenticacao_segundos: float = 10
    ws_intervalo_ping_segundos: float = 30
```

`.env.example`: `WS_TIMEOUT_AUTENTICACAO_SEGUNDOS=10` e `WS_INTERVALO_PING_SEGUNDOS=30`.

`src/app/notifications/websocket.py`:

```python
from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from fastapi import WebSocket, WebSocketDisconnect

from app.core.security import TokenInvalidoError, decodificar_token_com_expiracao
from app.domain.entities.usuario import Usuario
from app.notifications.barramento import Assinatura, BarramentoNotificacoes

CODIGO_NAO_AUTENTICADO = 4401


class _Sessao:
    def __init__(self, usuario_id: UUID, expira_em: datetime):
        self.usuario_id = usuario_id
        self.expira_em = expira_em


async def _validar(
    mensagem, buscar_usuario: Callable[[UUID], Usuario | None], jwt_secret_key: str
) -> tuple[UUID, datetime] | None:
    if not isinstance(mensagem, dict) or mensagem.get("tipo") != "autenticar":
        return None
    try:
        usuario_id, expira_em = decodificar_token_com_expiracao(
            str(mensagem.get("token", "")), jwt_secret_key
        )
    except TokenInvalidoError:
        return None
    usuario = await asyncio.to_thread(buscar_usuario, usuario_id)
    if usuario is None or not usuario.ativo:
        return None
    return usuario_id, expira_em


async def _repassar(websocket: WebSocket, assinatura: Assinatura) -> bool:
    while True:
        await websocket.send_json(await assinatura.proxima())


async def _pingar(websocket: WebSocket, intervalo: float) -> bool:
    while True:
        await asyncio.sleep(intervalo)
        await websocket.send_json({"tipo": "ping"})


async def _ler(
    websocket: WebSocket,
    sessao: _Sessao,
    buscar_usuario: Callable[[UUID], Usuario | None],
    jwt_secret_key: str,
) -> bool:
    while True:
        try:
            mensagem = await websocket.receive_json()
        except WebSocketDisconnect:
            return False
        except ValueError:
            continue
        if not isinstance(mensagem, dict) or mensagem.get("tipo") != "autenticar":
            continue
        validado = await _validar(mensagem, buscar_usuario, jwt_secret_key)
        if validado is None or validado[0] != sessao.usuario_id:
            return True
        sessao.expira_em = validado[1]
        await websocket.send_json({"tipo": "autenticado"})


async def _vigiar_expiracao(sessao: _Sessao) -> bool:
    while True:
        restante = (sessao.expira_em - datetime.now(UTC)).total_seconds()
        if restante <= 0:
            return True
        await asyncio.sleep(min(restante, 1.0))


async def atender_conexao(
    websocket: WebSocket,
    buscar_usuario: Callable[[UUID], Usuario | None],
    barramento: BarramentoNotificacoes,
    jwt_secret_key: str,
    timeout_autenticacao: float,
    intervalo_ping: float,
) -> None:
    await websocket.accept()
    try:
        primeira = await asyncio.wait_for(websocket.receive_json(), timeout_autenticacao)
    except WebSocketDisconnect:
        return
    except (TimeoutError, ValueError):
        await websocket.close(code=CODIGO_NAO_AUTENTICADO)
        return

    validado = await _validar(primeira, buscar_usuario, jwt_secret_key)
    if validado is None:
        await websocket.close(code=CODIGO_NAO_AUTENTICADO)
        return

    sessao = _Sessao(*validado)
    assinatura = await barramento.assinar(sessao.usuario_id)
    tarefas: list[asyncio.Task] = []
    try:
        await websocket.send_json({"tipo": "autenticado"})
        tarefas = [
            asyncio.create_task(_repassar(websocket, assinatura)),
            asyncio.create_task(_pingar(websocket, intervalo_ping)),
            asyncio.create_task(_ler(websocket, sessao, buscar_usuario, jwt_secret_key)),
            asyncio.create_task(_vigiar_expiracao(sessao)),
        ]
        concluidas, _ = await asyncio.wait(tarefas, return_when=asyncio.FIRST_COMPLETED)
        tarefa = next(iter(concluidas))
        if not tarefa.cancelled() and tarefa.exception() is None and tarefa.result() is True:
            await websocket.close(code=CODIGO_NAO_AUTENTICADO)
    finally:
        for tarefa in tarefas:
            tarefa.cancel()
        await asyncio.gather(*tarefas, return_exceptions=True)
        await assinatura.fechar()
```

`src/app/api/deps.py`:

```python
@lru_cache
def _redis_async_client(redis_url: str) -> redis.asyncio.Redis:
    return redis.asyncio.Redis.from_url(redis_url)


def get_barramento_notificacoes(
    settings: Settings = Depends(get_settings),
) -> BarramentoNotificacoes:
    return RedisBarramentoNotificacoes(
        _redis_client(settings.redis_url), _redis_async_client(settings.redis_url)
    )


def get_buscador_usuario(
    settings: Settings = Depends(get_settings),
) -> Callable[[UUID], Usuario | None]:
    fabrica = _session_factory(settings.database_url)

    def buscar(usuario_id: UUID) -> Usuario | None:
        with fabrica() as session:
            return SqlAlchemyUsuarioRepository(session).buscar_por_id(usuario_id)

    return buscar
```

(importe `redis.asyncio`, `Callable`, `BarramentoNotificacoes`, `RedisBarramentoNotificacoes`; ponha as funções depois de `_redis_client` e de `_session_factory`.)

`src/app/api/v1/controllers/notificacoes.py` — adicione:

```python
@router.websocket("/ws")
async def tempo_real(
    websocket: WebSocket,
    buscar_usuario: Callable[[UUID], Usuario | None] = Depends(get_buscador_usuario),
    barramento: BarramentoNotificacoes = Depends(get_barramento_notificacoes),
    settings: Settings = Depends(get_settings),
) -> None:
    await atender_conexao(
        websocket,
        buscar_usuario,
        barramento,
        jwt_secret_key=settings.jwt_secret_key,
        timeout_autenticacao=settings.ws_timeout_autenticacao_segundos,
        intervalo_ping=settings.ws_intervalo_ping_segundos,
    )
```

(imports: `WebSocket` de `fastapi`, `Callable`, `get_barramento_notificacoes`, `get_buscador_usuario`, `Settings`, `get_settings`, `BarramentoNotificacoes`, `atender_conexao`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/api/test_notificacoes_ws.py -q -p no:randomly && .venv/bin/pytest tests/unit tests/test_health.py -q && .venv/bin/ruff check src tests`
Expected: todos passam. Rode o arquivo do WebSocket 5 vezes seguidas (`for i in 1 2 3 4 5; do .venv/bin/pytest tests/unit/api/test_notificacoes_ws.py -q 2>&1 | tail -1; done`) e confirme que não há teste intermitente.

- [ ] **Step 5: Commit**

```bash
git add src/app/notifications/websocket.py src/app/api/v1/controllers/notificacoes.py src/app/api/deps.py src/app/core/config.py .env.example tests/unit/api/test_notificacoes_ws.py
```

Mensagem: `feat(notificacoes): adiciona WebSocket de notificacoes em tempo real`

---

### Task 5: Ligar o canal no service da API e do scheduler + verificação real

**Files:**
- Modify: `src/app/api/deps.py` (`get_notificacao_service`)
- Modify: `src/app/scheduler/jobs.py` (montagens de `NotificacaoService` em `_executar_ciclo` e `_executar_resumos_diarios`)
- Test: `tests/unit/api/test_deps.py`, `tests/unit/scheduler/test_jobs.py`

**Interfaces:**
- Consumes: `CanalTempoReal`, `RedisBarramentoNotificacoes`, `get_barramento_notificacoes` (Tasks 2–4).
- Produces: `get_notificacao_service(notificacao_repository, barramento)` com `[CanalTempoReal(barramento)]`; `jobs._notificacao_service(settings, notificacao_repository) -> NotificacaoService`.

- [ ] **Step 1: Write the failing tests**

Em `tests/unit/api/test_deps.py`:

```python
def test_notificacao_service_da_api_entrega_pelo_canal_tempo_real():
    barramento = FakeBarramentoNotificacoes()

    service = get_notificacao_service(
        notificacao_repository=FakeNotificacaoRepository(), barramento=barramento
    )
    notificacao = service.enviar_resumo_diario(uuid4(), "Resumo", {})

    assert barramento.publicados[0][0] == notificacao.usuario_id
```

Em `tests/unit/scheduler/test_jobs.py`:

```python
def test_notificacao_service_do_scheduler_tem_o_canal_tempo_real():
    service = _notificacao_service(Settings(_env_file=None), FakeNotificacaoRepository())

    assert [type(canal).__name__ for canal in service._canais] == ["CanalTempoReal"]
```

(com os imports `get_notificacao_service`, `FakeBarramentoNotificacoes`, `FakeNotificacaoRepository`, `_notificacao_service`; `uuid4` se faltar.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/unit/api/test_deps.py tests/unit/scheduler/test_jobs.py -q`
Expected: `TypeError: get_notificacao_service() got an unexpected keyword argument 'barramento'` e `ImportError` de `_notificacao_service`.

- [ ] **Step 3: Write minimal implementation**

`src/app/api/deps.py`:

```python
def get_notificacao_service(
    notificacao_repository: NotificacaoRepository = Depends(get_notificacao_repository),
    barramento: BarramentoNotificacoes = Depends(get_barramento_notificacoes),
) -> NotificacaoService:
    return NotificacaoService(notificacao_repository, canais=[CanalTempoReal(barramento)])
```

(`get_barramento_notificacoes` precisa estar definido antes; mova-o se necessário.)

`src/app/scheduler/jobs.py`:

```python
@lru_cache
def _redis_async_client(redis_url: str) -> redis.asyncio.Redis:
    return redis.asyncio.Redis.from_url(redis_url)


def _notificacao_service(
    settings: Settings, notificacao_repository: NotificacaoRepository
) -> NotificacaoService:
    barramento = RedisBarramentoNotificacoes(
        _redis_client(settings.redis_url), _redis_async_client(settings.redis_url)
    )
    return NotificacaoService(notificacao_repository, canais=[CanalTempoReal(barramento)])
```

e troque `NotificacaoService(notificacao_repository)` por `_notificacao_service(settings, notificacao_repository)` nas duas montagens (importe `redis.asyncio`, `NotificacaoRepository`, `RedisBarramentoNotificacoes`, `CanalTempoReal`).

O `client` da API (`tests/unit/api/conftest.py`) usa o `get_notificacao_service` real; para não tentar Redis nos testes existentes, adicione ao conftest uma fixture `barramento_notificacoes` (`FakeBarramentoNotificacoes()`) e o override `app.dependency_overrides[get_barramento_notificacoes] = lambda: barramento_notificacoes` na fixture `client`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit tests/test_health.py -q && .venv/bin/ruff check src tests`
Expected: todos passam.

- [ ] **Step 5: Verify for real**

Com o Redis descartável da Task 3 (`redis-ws`, porta 6382) e o pacote `websockets` instalado no venv (`.venv/bin/pip install websockets`), sem Postgres (o buscador de usuário é substituído):

```bash
PYTHONPATH=src:. .venv/bin/python - <<'EOF'
import asyncio, json, threading, time
from datetime import UTC, datetime
from uuid import uuid4
import uvicorn, websockets
from app.api.deps import get_buscador_usuario
from app.core.config import get_settings
from app.core.security import criar_token
from app.domain.entities.usuario import Usuario
from app.main import app
from app.services.notificacao_service import NotificacaoService
from app.api.deps import get_barramento_notificacoes
from app.notifications.canal import CanalTempoReal
from tests.fixtures.fake_notificacao_repository import FakeNotificacaoRepository

s = get_settings().model_copy(update={"redis_url": "redis://localhost:6382/0", "scheduler_habilitado": False})
app.dependency_overrides[get_settings] = lambda: s
u = Usuario.criar(id=uuid4(), nome="Ana", email="a@x.com", senha="segredo123", criado_em=datetime.now(UTC))
app.dependency_overrides[get_buscador_usuario] = lambda: (lambda uid: u if uid == u.id else None)
threading.Thread(target=uvicorn.run, args=(app,), kwargs={"port": 8765, "log_level": "warning"}, daemon=True).start()
time.sleep(1.5)

async def main():
    async with websockets.connect("ws://127.0.0.1:8765/api/v1/notificacoes/ws") as ws:
        await ws.send(json.dumps({"tipo": "autenticar", "token": criar_token(u.id, s.jwt_secret_key, 30)}))
        print("1:", await ws.recv())
        service = NotificacaoService(FakeNotificacaoRepository(), canais=[CanalTempoReal(get_barramento_notificacoes(s))])
        await asyncio.to_thread(service.enviar_resumo_diario, u.id, "Resumo de teste", {})
        print("2:", (await asyncio.wait_for(ws.recv(), 3))[:120])
asyncio.run(main())
EOF
```

Expected: `1: {"tipo": "autenticado"}` e `2: {"tipo": "notificacao", "notificacao": {"id": ...` com `"tipo": "RESUMO_DIARIO"`.

- [ ] **Step 6: Commit**

```bash
git add src/app/api/deps.py src/app/scheduler/jobs.py tests/unit/api/test_deps.py tests/unit/api/conftest.py tests/unit/scheduler/test_jobs.py
```

Mensagem: `feat(notificacoes): entrega notificacoes da API e do scheduler pelo WebSocket`
