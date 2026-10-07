# Web Push com VAPID (push 3/3) — design

## Contexto

A ERS pede que sinais técnicos e alertas disparados cheguem "através de web push, notificação mobile e notificação de sistema no desktop". Este é o último dos três subprojetos definidos em `2026-10-04-notificacoes-websocket-design.md`:

1. WebSocket em tempo real — pronto (`9e4dce3`).
2. Push mobile pela Expo — pronto (`c8cc982`), spec `2026-10-07-push-expo-design.md`.
3. **Web Push com VAPID (aba fechada) — este spec.**

Hoje (`develop` em `c8cc982`):

- `montar_canais(settings, barramento, dispositivo_repository, ticket_repository, cliente_expo)` em `app/notifications/canais.py` monta os canais do `NotificacaoService`, usado por `api/deps.py` e `scheduler/jobs.py`.
- `executar_com_retentativa(..., retentar_falha_de_rede=...)` permite não reenviar em timeout (evita push duplicado).
- `cryptography` 50.x já está instalado (dependência de `python-jose[cryptography]`).

## Decisões

1. **Mesmas regras do push Expo:** push em toda notificação, sem rastrear presença; envio síncrono dentro do canal; uma conta por inscrição (registrar uma inscrição de outra conta a transfere).
2. **Sem dependência nova** (abordagem B): cifragem RFC 8291 (`aes128gcm`) e JWT VAPID RFC 8292 escritos com `cryptography`; HTTP com httpx, limitador e retentativa do RNF-06. A cifragem é validada contra o vetor do apêndice A da RFC 8291.
3. **Inscrição morta é apagada**, não desativada: 404/410 do serviço de push significa que o endpoint não volta a existir.
4. **Lista permitida de hosts** para o `endpoint` (proteção contra SSRF): só `https` e hosts de serviços de push conhecidos, configurável por env.
5. **Payload igual ao do push Expo** (`title`, `body`, `data`), para os clientes reaproveitarem a lógica.
6. **Só a chave privada VAPID fica no env**; a pública é derivada dela.

Fora do escopo: confirmação de entrega, notificações com ações (botões), ícone/imagem no payload, múltiplos registros por payload (um único registro `aes128gcm`).

## Componentes

### Entidade — `src/app/domain/entities/inscricao_web_push.py`

```python
@dataclass
class InscricaoWebPush:
    id: UUID
    usuario_id: UUID
    endpoint: str
    p256dh: str
    auth: str
    criado_em: datetime
    atualizado_em: datetime
```

### Tabela e migration

Migration (`down_revision = "a3c5e7f9b1d2"`) cria `inscricoes_web_push`: `id` UUID PK, `usuario_id` UUID FK `usuarios.id` (`ON DELETE CASCADE`), `endpoint` `String(1024)` **único**, `p256dh` `String(255)`, `auth` `String(64)`, `criado_em`, `atualizado_em` (timestamptz). Índice em `usuario_id`. ORM em `src/app/db/models/inscricao_web_push.py`.

### Repositório (três partes)

`InscricaoWebPushRepository`:

- `buscar_por_endpoint(endpoint) -> InscricaoWebPush | None`
- `salvar(inscricao) -> None` (insert ou update)
- `listar_por_usuario(usuario_id) -> list[InscricaoWebPush]`
- `remover_por_endpoint(endpoint) -> None` (no-op se não existir)

### Validação — `src/app/integrations/web_push/validacao.py`

```python
def validar_inscricao(endpoint: str, p256dh: str, auth: str,
                      hosts_permitidos: list[str]) -> None: ...
```

Lança `InscricaoWebPushInvalidaError` quando:

- `endpoint` com mais de 1024 caracteres, esquema diferente de `https`, com usuário/senha na URL, com porta inválida ou diferente de 443, ou com host fora da lista. Um item da lista que começa com `*.` aceita qualquer subdomínio (não o domínio puro); os demais exigem host idêntico. A comparação usa o host já interpretado pela URL (`urllib.parse`), em minúsculas — `fcm.googleapis.com.evil.com` e `evil.com/fcm.googleapis.com` são recusados.
- `p256dh` que não decodifica (base64url), não tem 65 bytes, não começa com `0x04` ou não é ponto da curva P-256.
- `auth` que não decodifica ou não tem 16 bytes.

Lista padrão (`WEB_PUSH_HOSTS_PERMITIDOS`): `fcm.googleapis.com`, `updates.push.services.mozilla.com`, `*.push.apple.com`, `*.notify.windows.com`.

### Cifragem — `src/app/integrations/web_push/cifragem.py`

```python
TAMANHO_REGISTRO = 4096
TAMANHO_MAXIMO_PAYLOAD = 3993

def cifrar(texto: bytes, p256dh: str, auth: str,
           chave_efemera: ec.EllipticCurvePrivateKey | None = None,
           salt: bytes | None = None) -> bytes: ...
```

RFC 8291: ECDH entre a chave efêmera e `p256dh`; `IKM = HKDF(salt=auth, ikm=ecdh, info="WebPush: info\0" || ua_public || as_public, 32)`; `CEK = HKDF(salt, IKM, "Content-Encoding: aes128gcm\0", 16)`; `NONCE = HKDF(salt, IKM, "Content-Encoding: nonce\0", 12)`; AES-128-GCM sobre `texto || 0x02`. Corpo: `salt(16) || rs(uint32 4096) || idlen(1)=65 || as_public(65) || ciphertext`. `chave_efemera` e `salt` só são passados nos testes (vetor da RFC); em produção são gerados a cada chamada. Texto maior que `TAMANHO_MAXIMO_PAYLOAD` → `ValueError`.

### VAPID — `src/app/integrations/web_push/vapid.py`

```python
class ChaveVapid:
    @classmethod
    def de_base64url(cls, chave_privada: str) -> "ChaveVapid": ...
    @classmethod
    def gerar(cls) -> "ChaveVapid": ...
    def privada_base64url(self) -> str: ...
    def publica_base64url(self) -> str: ...
    def cabecalho_authorization(self, endpoint: str, contato: str, agora: datetime) -> str: ...
```

- Chave privada no env: escalar P-256 de 32 bytes em base64url (formato dos geradores comuns de VAPID).
- JWT ES256 com header `{"typ":"JWT","alg":"ES256"}` e claims `aud` = origem do endpoint (`scheme://host[:porta]`), `exp` = `agora + 12h` (inteiro), `sub` = contato. Assinatura convertida de DER para `r||s` (64 bytes).
- Header: `vapid t=<jwt>, k=<chave pública base64url>`.
- Script `python -m app.scripts.gerar_chaves_vapid` imprime `WEB_PUSH_VAPID_CHAVE_PRIVADA=...` e a chave pública.

### Cliente — `src/app/integrations/web_push/client.py`

```python
class ResultadoWebPush(str, Enum):
    ENTREGUE = "ENTREGUE"
    INSCRICAO_EXPIRADA = "INSCRICAO_EXPIRADA"
    RECUSADO = "RECUSADO"

class WebPushIndisponivelError(Exception): ...

class WebPushClient:
    def __init__(self, http_client, chave: ChaveVapid, contato: str, ttl_segundos: int,
                 limitador=None, politica=POLITICA_PADRAO, dormir=time.sleep,
                 agora=lambda: datetime.now(UTC)): ...
    def enviar(self, endpoint: str, p256dh: str, auth: str, payload: dict) -> ResultadoWebPush: ...
```

- Cifra `json.dumps(payload)` e faz `POST endpoint` (URL absoluta) com headers `Content-Encoding: aes128gcm`, `Content-Type: application/octet-stream`, `TTL: <ttl>`, `Urgency: high`, `Authorization: vapid ...`.
- Retentativa: só `ConnectError` entre as falhas de rede (timeout não reenvia), 429 e 5xx.
- 201/202 (e qualquer 2xx) → `ENTREGUE`; 404/410 → `INSCRICAO_EXPIRADA`; 401/403 → log ERROR (VAPID mal configurado) e `RECUSADO`; outros 4xx (incluindo 413) → log WARNING e `RECUSADO`; erro após retentativas, limitador sem vaga ou falha de rede → `WebPushIndisponivelError`.
- O endpoint nunca vai para o log (identifica o navegador); o log usa só o host.

### Canal — `src/app/notifications/canal_web_push.py`

```python
class CanalWebPush(CanalNotificacao):
    def __init__(self, inscricao_repository, cliente: WebPushClient): ...
    def entregar(self, notificacao: Notificacao) -> None: ...
```

1. Lista as inscrições do usuário; vazio → retorna sem enviar.
2. Payload: `{"title", "body", "data": {"notificacao_id", "tipo", "ativo_id"}}`, títulos iguais ao push Expo ("Sinal técnico", "Alerta de preço", "Resumo diário").
3. Para cada inscrição: `enviar`; `INSCRICAO_EXPIRADA` → `remover_por_endpoint`; `WebPushIndisponivelError` → log WARNING e segue para a próxima.
4. Log `evento: "push_web_enviado"` com `usuario_id`, `notificacao_id`, `inscricoes`, `entregues`, `expiradas`, `falhas`.

### Serviço — `src/app/services/inscricao_web_push_service.py`

```python
class InscricaoWebPushService:
    def __init__(self, inscricao_repository, hosts_permitidos: list[str],
                 agora=lambda: datetime.now(UTC)): ...
    def registrar(self, usuario_id: UUID, endpoint: str, p256dh: str, auth: str) -> bool: ...
    def remover(self, usuario_id: UUID, endpoint: str) -> None: ...
```

- `registrar` valida (→ `InscricaoWebPushInvalidaError`), faz upsert pelo endpoint, transfere de conta se preciso e atualiza `p256dh`/`auth`; devolve `True` se criou. Loga `evento: "inscricao_web_push_registrada"` com `usuario_id` e `transferida`.
- `remover` apaga apenas se a inscrição for do usuário.

### Endpoints — `src/app/api/v1/controllers/web_push.py`

| Método | Rota | Auth | Body / query | Resposta |
|---|---|---|---|---|
| GET | `/api/v1/web-push/chave-publica` | público | — | 200 `{"chave_publica": "..."}`; 503 `"Web push nao configurado"` |
| POST | `/api/v1/web-push/inscricoes` | 🔒 | `{"endpoint", "keys": {"p256dh", "auth"}}` (`expirationTime` ignorado) | 201 / 200 `{"endpoint"}`; 422 `"Inscricao de web push invalida"` |
| DELETE | `/api/v1/web-push/inscricoes` | 🔒 | `?endpoint=...` | 204 |

### Configuração — `core/config.py`

| Campo | Env | Padrão |
|---|---|---|
| `web_push_habilitado` | `WEB_PUSH_HABILITADO` | `True` |
| `web_push_vapid_chave_privada` | `WEB_PUSH_VAPID_CHAVE_PRIVADA` | `""` |
| `web_push_vapid_contato` | `WEB_PUSH_VAPID_CONTATO` | `""` |
| `web_push_hosts_permitidos` | `WEB_PUSH_HOSTS_PERMITIDOS` | os quatro hosts acima (JSON) |
| `web_push_requisicoes_por_minuto` | `WEB_PUSH_REQUISICOES_POR_MINUTO` | `300` |
| `web_push_ttl_segundos` | `WEB_PUSH_TTL_SEGUNDOS` | `86400` |

`Settings.web_push_configurado()` é verdadeiro só com habilitado, chave privada válida e contato começando com `mailto:` ou `https://` (exigência do `sub` do VAPID). Fábrica `criar_web_push_client(settings) -> WebPushClient | None` em `app/integrations/web_push/fabrica.py` (None quando não configurado).

### Ligação

`montar_canais` ganha os parâmetros `inscricao_repository` e `cliente_web_push: WebPushClient | None`; acrescenta `CanalWebPush` quando `cliente_web_push` não é `None`. `api/deps.py` e `scheduler/jobs.py` passam o repositório da sessão e `criar_web_push_client(settings)`.

## Testes

Unitários:

- `cifragem`: vetor do apêndice A da RFC 8291 bate byte a byte; ida e volta com chaves geradas (decifra com a chave do "navegador"); texto acima do limite → `ValueError`.
- `vapid`: header ES256 e claims `aud`/`exp`/`sub`; assinatura verifica com a chave pública; pública derivada da privada; `gerar` → `de_base64url` ida e volta; `aud` inclui a porta quando não padrão.
- `validacao`: endpoint `http`, host fora da lista, `fcm.googleapis.com.evil.com`, `evil.com/fcm.googleapis.com`, URL com usuário, endpoint longo, `p256dh` inválido/fora da curva/tamanho errado, `auth` com tamanho errado → recusados; `fcm.googleapis.com` e `xyz.push.apple.com` aceitos; `push.apple.com` puro recusado com `*.push.apple.com`.
- `WebPushClient` (`httpx.MockTransport`): headers; corpo decifrável pela chave do navegador; 201 → ENTREGUE; 404 e 410 → INSCRICAO_EXPIRADA; 401 → RECUSADO com log ERROR; 429 retentado; timeout não retentado; falha final → `WebPushIndisponivelError`.
- `CanalWebPush`: sem inscrições não envia; payload; expirada removida; falha numa inscrição não impede a próxima; log sem endpoint.
- `InscricaoWebPushService`: cria; repete (200) e atualiza chaves; transfere de conta; inválida não salva; `remover` só do dono e idempotente.
- Endpoints: 201, 200, 422, 401 sem token, 204, `chave-publica` 200 e 503.
- Config/`montar_canais`/jobs: padrões; canal incluído só quando configurado.

Integração (Postgres descartável): repositório e migration `upgrade`/`downgrade`.

Smoke real: `POST` para um endpoint FCM inexistente com VAPID válido; esperado 404/410 (ou 400/403 informativo — o resultado é registrado). Entrega real depende de um navegador com service worker.

## Entrega aos times

- Chaves VAPID geradas pelo script e gravadas no `.env` local, com `WEB_PUSH_VAPID_CONTATO=mailto:insightflow@example.com` (placeholder: o `sub` vai para os serviços de push em todo envio; o responsável troca pelo contato real do projeto). A porta padrão 443 é omitida do `aud`.
- `.env.example` com as variáveis `WEB_PUSH_*` (chave vazia).
- `docs/api-reference.html`: seção "Web Push" com os endpoints, o roteiro do front (buscar `chave-publica`, registrar service worker, `pushManager.subscribe({ userVisibleOnly: true, applicationServerKey })`, `POST /web-push/inscricoes` a cada login, `DELETE` antes do logout), um service worker mínimo (`push` → `showNotification`, `notificationclick` → abrir a tela e marcar como lida) e os avisos: exige HTTPS (em dev `localhost` funciona) e no Safari/iOS só com o site instalado na tela inicial.
