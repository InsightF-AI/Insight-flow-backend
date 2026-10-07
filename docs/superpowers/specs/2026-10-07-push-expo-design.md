# Push mobile pela Expo (push 2/3) — design

## Contexto

A ERS pede que sinais técnicos (RF de notificação de sinais) e alertas personalizados disparados sejam entregues "através de web push, notificação mobile e notificação de sistema no desktop". O app mobile é React Native com Expo SDK 54 e Expo Notifications.

O push foi dividido em três subprojetos no spec `2026-10-04-notificacoes-websocket-design.md`:

1. WebSocket em tempo real — pronto (`9e4dce3`).
2. **Push mobile pela Expo Push API (app fechado) — este spec.**
3. Web push com VAPID (aba fechada) — ciclo próprio, depois deste.

Hoje (`develop` em `b472d0c`):

- `NotificacaoService` persiste a notificação e chama `_distribuir`, que entrega para cada `CanalNotificacao` da lista e isola falhas de canal (log WARNING, segue).
- A única implementação é `CanalTempoReal` (Redis pub/sub → WebSocket). A lista de canais é montada em `api/deps.py` e `scheduler/jobs.py`.
- Notificações nascem só no scheduler (sinal ativado, alerta disparado, resumo diário), nunca no caminho de uma requisição do usuário.
- As integrações HTTP usam `LimitadorTaxa` + `executar_com_retentativa` (RNF-06) e logs JSON com correlation id (RNF-11).

## Decisões

1. **Push em toda notificação.** O backend não rastreia presença. Com o app em primeiro plano, o próprio app suprime o banner (`Notifications.setNotificationHandler`) e usa o que chegou pelo WebSocket.
2. **Envio síncrono dentro do canal** (abordagem A). Uma chamada HTTP por notificação no thread do scheduler, sem fila no Redis nem worker. Volume atual não justifica fila.
3. **httpx próprio, sem `exponent-server-sdk`.** Mantém o padrão das demais integrações (limitador, retentativa, erros de domínio).
4. **Tickets conferidos por job.** O erro `DeviceNotRegistered` costuma aparecer só nos recibos; um job periódico os consulta e desativa tokens mortos.
5. **Tickets em tabela, não no Redis.** Sobrevivem a restart; a tabela é esvaziada pelo próprio job.
6. **Um token pertence a no máximo um usuário.** Registrar um token já ligado a outra conta o transfere para a conta atual.

Fora do escopo: Web Push (3/3), notificação de bandeja do desktop (o app desktop usa o WebSocket), preferência de push por tipo de notificação, listagem de dispositivos (`GET`), campo de plataforma iOS/Android e expurgo de tokens inativos.

## Componentes

### Entidades — `src/app/domain/entities/`

`dispositivo_push.py`:

```python
@dataclass
class DispositivoPush:
    id: UUID
    usuario_id: UUID
    token: str
    ativo: bool
    criado_em: datetime
    atualizado_em: datetime
```

`ticket_push.py`:

```python
@dataclass(frozen=True)
class TicketPush:
    id: str
    token: str
    criado_em: datetime
```

### Tabelas e migration

Uma migration Alembic (`down_revision = "f1a7c3e9b2d4"`) cria:

- `dispositivos_push`: `id` UUID PK, `usuario_id` UUID FK `usuarios.id` (`ON DELETE CASCADE`), `token` `String(255)` **único**, `ativo` bool, `criado_em`, `atualizado_em` (timestamptz). Índice em `(usuario_id, ativo)`.
- `tickets_push`: `id` `String(64)` PK (id do ticket da Expo), `token` `String(255)`, `criado_em` timestamptz. Índice em `criado_em`.

Modelos ORM em `src/app/db/models/dispositivo_push.py` e `ticket_push.py`.

### Repositórios (três partes cada, padrão do projeto)

`DispositivoPushRepository` (`repositories/interfaces/`, `repositories/sqlalchemy/`, `tests/fixtures/fake_dispositivo_push_repository.py`):

- `buscar_por_token(token) -> DispositivoPush | None`
- `salvar(dispositivo) -> None` (insert ou update)
- `listar_ativos_por_usuario(usuario_id) -> list[DispositivoPush]`
- `desativar_por_token(token, agora) -> None` (no-op se não existir)

`TicketPushRepository` (mesmas três partes):

- `salvar_muitos(tickets) -> None`
- `listar_anteriores_a(limite: datetime, quantidade: int) -> list[TicketPush]` (mais antigos primeiro)
- `remover_muitos(ids) -> None`

### Serviço — `src/app/services/dispositivo_push_service.py`

```python
class DispositivoPushService:
    def registrar(self, usuario_id: UUID, token: str) -> bool: ...
    def remover(self, usuario_id: UUID, token: str) -> None: ...
```

- Formato aceito: `^(ExponentPushToken|ExpoPushToken)\[[^\]]+\]$`, até 255 caracteres. Fora disso, `TokenPushInvalidoError` (→ 422).
- `registrar` devolve `True` se criou e `False` se o token já existia. Se existia: passa `usuario_id` para o usuário atual, `ativo = True`, atualiza `atualizado_em`. Loga `evento: "dispositivo_registrado"` com `usuario_id` e se houve transferência de conta (nunca o token).
- `remover` desativa apenas se o token pertencer ao `usuario_id`. Token desconhecido ou de outro usuário: não faz nada (idempotente).

### Endpoints — `src/app/api/v1/controllers/dispositivos.py`

| Método | Rota | Body / query | Resposta |
|---|---|---|---|
| POST | `/api/v1/dispositivos` | `{"token": "ExponentPushToken[...]"}` | 201 (criado) ou 200 (já existia), corpo `{"token", "ativo"}` |
| DELETE | `/api/v1/dispositivos` | `?token=ExponentPushToken[...]` | 204 |

Ambos exigem autenticação. Formato inválido → 422 `"Token de push invalido"`.

### Integração — `src/app/integrations/expo/client.py`

```python
@dataclass(frozen=True)
class ResultadoEnvio:
    token: str
    ticket_id: str | None
    erro: str | None

@dataclass(frozen=True)
class ReciboPush:
    status: str
    erro: str | None

class ExpoIndisponivelError(Exception): ...

class ExpoPushClient:
    def __init__(self, http_client, access_token=None, limitador=None,
                 politica=POLITICA_PADRAO, dormir=time.sleep): ...
    def enviar(self, mensagens: list[dict]) -> list[ResultadoEnvio]: ...
    def buscar_recibos(self, ids: list[str]) -> dict[str, ReciboPush]: ...
```

- `enviar`: `POST /--/api/v2/push/send` em lotes de até 100 mensagens; os itens de `data` voltam na mesma ordem. `erro` é `details.error` do ticket (ex: `DeviceNotRegistered`), ou `"desconhecido"` quando o status é `error` sem detalhe.
- `buscar_recibos`: `POST /--/api/v2/push/getReceipts` com até 1000 ids por chamada; ids ausentes na resposta não entram no dicionário.
- Headers: `Accept: application/json`, `Content-Type: application/json` e, se configurado, `Authorization: Bearer <EXPO_ACCESS_TOKEN>`.
- Limitador compartilhado `"expo"` e `executar_com_retentativa` (429/5xx/rede). No envio, falha de rede só é retentada se for de conexão (`ConnectError`): timeout de leitura não é reenviado, porque a Expo pode já ter aceitado o lote e o reenvio duplicaria o push. A consulta de recibos retenta qualquer falha de rede. Erro HTTP final, `LimiteTaxaExcedidoError` ou corpo com `errors` no nível da requisição → `ExpoIndisponivelError`.

### Canal — `src/app/notifications/canal_expo.py`

```python
class CanalExpo(CanalNotificacao):
    def __init__(self, dispositivo_repository, ticket_repository, cliente: ExpoPushClient,
                 agora=lambda: datetime.now(UTC)): ...
    def entregar(self, notificacao: Notificacao) -> None: ...
```

1. Lista os dispositivos ativos do usuário; se vazio, retorna sem chamar a Expo.
2. Monta uma mensagem por token:

```json
{
  "to": "ExponentPushToken[xxx]",
  "title": "Alerta de preço",
  "body": "<notificacao.mensagem>",
  "data": {"notificacao_id": "...", "tipo": "ALERTA_DISPARADO", "ativo_id": "... ou null"},
  "sound": "default",
  "priority": "high"
}
```

   Títulos: `SINAL_ATIVADO` → "Sinal técnico"; `ALERTA_DISPARADO` → "Alerta de preço"; `RESUMO_DIARIO` → "Resumo diário".
3. Para cada `ResultadoEnvio`: ticket ok → acumula `TicketPush`; erro `DeviceNotRegistered` → `desativar_por_token`; outro erro → log WARNING com o código do erro.
4. Salva os tickets acumulados com `salvar_muitos`.
5. Loga `evento: "push_enviado"` com `usuario_id`, `notificacao_id`, quantidade de tokens e de erros.

`ExpoIndisponivelError` sobe e é isolado por `NotificacaoService._distribuir`.

### Job de recibos — `src/app/scheduler/recibos_push.py`

```python
def conferir_recibos_push(ticket_repository, dispositivo_repository, cliente,
                          agora: datetime, lote: int = 1000) -> None: ...
```

Registrado em `registrar_jobs` como `recibos_push` (intervalo `EXPO_RECIBOS_INTERVALO_MINUTOS`, padrão 30), dentro de `executar_job`, só quando `EXPO_PUSH_HABILITADO`. Em loop, enquanto houver tickets com `criado_em <= agora - 15 min`:

| Recibo | Ação |
|---|---|
| `ok` | remove o ticket |
| `error` + `DeviceNotRegistered` | desativa o token e remove o ticket |
| `error` + `InvalidCredentials` | log ERROR e remove o ticket |
| `error` com outro código | log WARNING e remove o ticket |
| ausente e ticket com menos de 24 h | mantém |
| ausente e ticket com 24 h ou mais | remove |

O loop termina quando um lote não remove nenhum ticket (só pendentes) ou quando não há mais tickets elegíveis. Ao final loga `evento: "recibos_push_conferidos"` com verificados, tokens desativados e pendentes.

### Configuração — `core/config.py`

| Campo | Env | Padrão |
|---|---|---|
| `expo_push_habilitado` | `EXPO_PUSH_HABILITADO` | `True` |
| `expo_base_url` | `EXPO_BASE_URL` | `"https://exp.host"` |
| `expo_access_token` | `EXPO_ACCESS_TOKEN` | `""` |
| `expo_requisicoes_por_minuto` | `EXPO_REQUISICOES_POR_MINUTO` | `300` |
| `expo_recibos_intervalo_minutos` | `EXPO_RECIBOS_INTERVALO_MINUTOS` | `30` |

### Ligação

Em `api/deps.py` (`get_notificacao_service`) e `scheduler/jobs.py` (`_notificacao_service`), a lista de canais vira `[CanalTempoReal(...), CanalExpo(...)]` quando `expo_push_habilitado`, e continua `[CanalTempoReal(...)]` quando não. O `CanalExpo` usa os repositórios na mesma sessão do `NotificacaoService`.

## Testes

Unitários (com Fakes, sem rede):

- `DispositivoPushService`: cria; reativa inativo; transfere de outra conta; recusa formato inválido; `remover` ignora token de outro usuário; `remover` idempotente.
- `ExpoPushClient` (`httpx.MockTransport`): lotes de 100; tickets ok/error; `Authorization` só quando configurado; 429 retentado; `errors` no nível da requisição → `ExpoIndisponivelError`; recibos parseados.
- `CanalExpo`: sem tokens não chama a Expo; `DeviceNotRegistered` desativa; ticket ok persistido; título, corpo e `data` por tipo.
- `conferir_recibos_push`: uma linha da tabela por teste; múltiplos lotes; para quando só restam pendentes.
- Controller `/dispositivos`: 201, 200, 422, 204, 401 sem token, transferência entre contas.
- Config e jobs: padrões novos; job `recibos_push` registrado só com push habilitado; canais montados conforme a flag.

Integração (Postgres descartável em :5434): os dois repositórios SQLAlchemy; migration `upgrade`/`downgrade`.

Smoke real: enviar para um token com formato válido e inexistente; a Expo responde ticket `error`/`DeviceNotRegistered`, o que valida o contrato de request e response e a desativação do token sem aparelho físico.

## Entrega aos times

`docs/api-reference.html` ganha a seção "Dispositivos (push)" com os endpoints, o payload do push, o significado de `data` e o roteiro do app:

1. Pedir permissão de notificação.
2. Gerar o token com `getExpoPushTokenAsync({ projectId })` e enviar em `POST /dispositivos` a cada login e quando o token mudar.
3. Chamar `DELETE /dispositivos?token=...` antes de `POST /auth/logout`.
4. Em primeiro plano, suprimir o banner com `setNotificationHandler` (o WebSocket já entrega).
5. Ao tocar no push, abrir a tela por `data.tipo`/`data.ativo_id` e chamar `PATCH /notificacoes/{data.notificacao_id}/lida`.

`.env.example` ganha as variáveis `EXPO_*`.
