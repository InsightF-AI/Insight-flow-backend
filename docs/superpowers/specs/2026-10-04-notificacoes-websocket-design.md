# Notificações em tempo real (WebSocket) — design

## Contexto

RF-09 e RF-18 pedem que alertas de sinal e de alertas personalizados cheguem ao usuário pelos canais disponíveis. O UC-05 descreve o fluxo: o serviço de notificação distribui a mensagem aos clientes conectados; se o usuário estiver offline em todos os clientes, o alerta fica pendente e é entregue no próximo login.

Hoje (`develop` em 2026-10-04, `a35f45f`):

- `NotificacaoService` grava `Notificacao` no banco em `enviar_alerta`, `enviar_alerta_personalizado` e `enviar_resumo_diario`.
- Os clientes só veem notificações consultando `GET /api/v1/notificacoes` (com `apenas_nao_lidas`) e marcando com `PATCH /{id}/lida`. O fluxo offline do UC-05 já funciona por aí.
- `src/app/notifications/` existe mas está vazio.
- Os clientes (web React, mobile Expo, desktop WinForms) ainda não existem; o backend define o contrato.

O push foi dividido em três subprojetos, nesta ordem:

1. **Canal em tempo real por WebSocket** (este documento) — atende os três clientes com o app aberto.
2. Push mobile pela Expo Push API (app fechado).
3. Web push com VAPID (aba fechada).

Os subprojetos 2 e 3 entram depois como novos `CanalNotificacao`, sem mudar o `NotificacaoService`.

## Decisões

1. **WebSocket** (e não SSE), escolhido pelo usuário; deixa o canal pronto para futuros usos bidirecionais.
2. **Autenticação pela primeira mensagem**, não por query string nem header: navegadores não permitem header em WebSocket, e token em URL vai parar em logs.
3. **Fan-out por Redis pub/sub.** O scheduler roda em threads e as conexões no loop asyncio; o Redis faz a ponte entre os dois e já funciona com vários workers.
4. **Sem fila por conexão.** O socket só entrega o que acontece enquanto está aberto. Ao conectar ou reconectar, o cliente busca as pendentes por `GET /notificacoes?apenas_nao_lidas=true`.
5. **Entrega é melhor esforço.** A notificação é gravada antes; falha de canal só gera aviso no log e nunca interrompe o ciclo do scheduler nem a requisição.

Fora do escopo: Expo push, Web push, confirmação de entrega (ack), reenvio pelo socket de mensagens perdidas e streaming do chat de IA.

## Protocolo

Endpoint: `WS /api/v1/notificacoes/ws`.

Mensagens do cliente para o servidor:

| Mensagem | Efeito |
|---|---|
| `{"tipo": "autenticar", "token": "<access_token>"}` | Primeira mensagem obrigatória, em até `ws_timeout_autenticacao_segundos` (padrão 10). Pode ser reenviada a qualquer momento com um token novo (reautenticação). |
| qualquer outra | Ignorada. |

Mensagens do servidor para o cliente:

| Mensagem | Quando |
|---|---|
| `{"tipo": "autenticado"}` | Depois de cada autenticação válida. |
| `{"tipo": "notificacao", "notificacao": {...}}` | A cada notificação nova do usuário. O objeto tem o mesmo formato JSON de `NotificacaoResponse` (`id`, `ativo_id`, `tipo`, `mensagem`, `contexto`, `lida`, `criado_em`). |
| `{"tipo": "ping"}` | A cada `ws_intervalo_ping_segundos` (padrão 30). |

Fechamento com código `4401` quando:

- a primeira mensagem não é `autenticar` ou não chega dentro do prazo;
- o token é inválido (`decodificar_token` lança `TokenInvalidoError`);
- o usuário não existe ou está com `ativo=False`;
- uma reautenticação traz token inválido;
- o `exp` do token da sessão passa sem reautenticação.

Vários sockets do mesmo usuário (web, mobile e desktop) recebem todas as notificações.

## Componentes

Todos em `src/app/notifications/`, salvo indicação.

### `barramento.py`

```python
class BarramentoNotificacoes(ABC):
    @abstractmethod
    def publicar(self, usuario_id: UUID, payload: dict) -> None: ...

    @abstractmethod
    def assinar(self, usuario_id: UUID) -> AsyncIterator[dict]: ...
```

- `publicar` é síncrono (chamado pelo service, inclusive em thread do scheduler).
- `assinar` devolve um iterador assíncrono que termina quando o consumidor o fecha (`aclose`).

### `redis_barramento.py`

`RedisBarramentoNotificacoes(redis_sync: redis.Redis, redis_async: redis.asyncio.Redis)`:

- canal `notificacoes:{usuario_id}`;
- `publicar` faz `redis_sync.publish(canal, json.dumps(payload))`;
- `assinar` usa `redis_async.pubsub()`, `subscribe(canal)` e itera `listen()`, devolvendo `json.loads` de cada mensagem do tipo `message`; ao fechar, faz `unsubscribe` e fecha o pubsub.

### `canal.py`

```python
class CanalNotificacao(ABC):
    @abstractmethod
    def entregar(self, notificacao: Notificacao) -> None: ...


class CanalTempoReal(CanalNotificacao):
    def __init__(self, barramento: BarramentoNotificacoes): ...
    def entregar(self, notificacao: Notificacao) -> None:
        self._barramento.publicar(
            notificacao.usuario_id, {"tipo": "notificacao", "notificacao": notificacao_para_dict(notificacao)}
        )
```

### `serializacao.py`

`notificacao_para_dict(notificacao: Notificacao) -> dict` com valores JSON (UUIDs e datas em string ISO 8601, `tipo` como string). Deve ser igual a `NotificacaoResponse.de(notificacao).model_dump(mode="json")`; um teste garante isso.

### `websocket.py`

`async def atender_conexao(websocket, usuario_repository, barramento, jwt_secret_key, timeout_autenticacao, intervalo_ping, agora=...)`:

1. `accept()`.
2. Espera a primeira mensagem com `asyncio.wait_for(..., timeout_autenticacao)`; valida; em falha, `close(4401)`.
3. Envia `autenticado`, abre `barramento.assinar(usuario_id)` e roda três tarefas concorrentes até a primeira terminar:
   - repassar cada payload do barramento para o socket;
   - enviar `ping` a cada `intervalo_ping`;
   - ler mensagens do cliente: `autenticar` válido atualiza o `exp` da sessão e responde `autenticado`; inválido fecha com 4401; desconexão encerra.
   - O vencimento do `exp` (sem reautenticação) também fecha com 4401.
4. Ao sair, cancela as tarefas e fecha a assinatura.

Para ler o `exp`, `core/security.py` ganha `decodificar_token_com_expiracao(token, secret_key) -> tuple[UUID, datetime]`, com o mesmo tratamento de erro de `decodificar_token`.

### `NotificacaoService` (`src/app/services/notificacao_service.py`)

- Construtor: `NotificacaoService(notificacao_repository, canais: Sequence[CanalNotificacao] = ())`.
- Depois de cada `salvar` em `enviar_alerta`, `enviar_alerta_personalizado` e `enviar_resumo_diario`, chama `canal.entregar(notificacao)` para cada canal; exceções viram `logger.warning(..., exc_info=True)` e o próximo canal é tentado.
- `marcar_como_lida` não publica nada.

### API, montagem e configuração

- `controllers/notificacoes.py`: `@router.websocket("/ws")` que chama `atender_conexao` com as dependências.
- `deps.py`: `get_barramento_notificacoes(settings)` (Redis síncrono e assíncrono com `lru_cache` por URL) e `get_notificacao_service` passando `[CanalTempoReal(barramento)]`.
- `jobs.py`: as duas montagens de `NotificacaoService` (ciclo de monitoramento e resumo diário) recebem o mesmo canal.
- `Settings`: `ws_timeout_autenticacao_segundos: float = 10`, `ws_intervalo_ping_segundos: float = 30`; `.env.example` atualizado.
- Dependência: `websockets` já vem com `uvicorn[standard]` (imagem Docker). O `.venv` local precisa de `pip install -r requirements.txt` atualizado para o teste real.

## Testes

- **Service:** publica em cada canal depois de salvar, nos três métodos; falha de um canal não impede a gravação nem os demais canais; `marcar_como_lida` não publica.
- **Serialização:** igual a `NotificacaoResponse.de(...).model_dump(mode="json")`, inclusive com `ativo_id=None`.
- **WebSocket** (`TestClient.websocket_connect`, `FakeBarramentoNotificacoes`, prazos curtos):
  - token válido → `autenticado`;
  - token inválido, usuário inativo, primeira mensagem errada e silêncio além do prazo → fechamento 4401;
  - notificação do usuário chega; a de outro usuário não;
  - dois sockets do mesmo usuário recebem a mesma notificação;
  - `ping` chega no intervalo configurado;
  - reautenticação com token novo responde `autenticado` e mantém a conexão; com token inválido fecha 4401;
  - token cujo `exp` passa sem reautenticação fecha 4401.
- **Fluxo completo (unit):** um alerta personalizado disparado pelo ciclo de monitoramento chega ao socket aberto do dono.
- **Integração** (`-m integration`, Redis em porta descartável): `publicar` → `assinar` entrega o payload; canal de outro usuário não recebe.
- **Verificação real:** API com `uvicorn` + Redis descartável; cliente WebSocket real autentica, recebe `autenticado` e recebe uma notificação publicada pelo service.

## Riscos

- **Sem Redis, sem tempo real.** O `GET /notificacoes` continua funcionando; o socket fecha (ou nem assina) e o cliente cai no polling ao reconectar.
- **Proxies e load balancers** precisam permitir upgrade para WebSocket e timeout ocioso acima de `ws_intervalo_ping_segundos`.
- **Uma conexão Redis de pub/sub por socket aberto.** Adequado para o volume do projeto; com muitos usuários, trocar por uma assinatura única por processo com roteamento local.
