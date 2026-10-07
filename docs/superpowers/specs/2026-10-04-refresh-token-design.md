# Refresh token — design

## Contexto

RNF-04 da ERS: "A comunicação entre clientes e API deve ser autenticada por JWT com expiração máxima de 24 horas e mecanismo de refresh token."

Hoje (`develop` em 2026-10-04):

- `POST /api/v1/usuarios` (cadastro) e `POST /api/v1/auth/login` devolvem `TokenResponse(access_token, token_type="bearer")`.
- O access token é um JWT HS256 com `sub` e `exp`, gerado por `core/security.criar_token`, com validade `jwt_expiration_minutes = 1440` (24h).
- Não existe refresh token, logout nem revogação.

Esta é a terceira parte do "pacote clientes" (CORS, fallback da análise IA e refresh token), feito antes dos clientes web, mobile e desktop crescerem, porque muda o contrato de autenticação que os três usam.

## Decisões

1. **Refresh token persistido com rotação** (e não JWT stateless). Permite logout real e detectar o reuso de um token roubado.
2. **Token opaco.** `secrets.token_urlsafe(48)`. No banco fica só o SHA-256 (hex) do token, nunca o token em si.
3. **Famílias.** Todos os tokens que nascem de um mesmo login ou cadastro compartilham um `familia_id`. Reuso de um token já revogado revoga a família inteira.
4. **Validades padrão.** Access token: 30 minutos (`JWT_EXPIRATION_MINUTES=30`, era 1440). Refresh token: 30 dias (`REFRESH_TOKEN_EXPIRACAO_DIAS=30`). Os dois são configuráveis; a ERS só exige access token de no máximo 24h.
5. **Compatível com clientes atuais.** O `TokenResponse` só ganha campos; `access_token` e `token_type` continuam iguais, e `get_usuario_atual` não muda.

Fora do escopo: limpeza periódica de tokens expirados, listagem de sessões ativas e encerramento por dispositivo.

## Componentes

### Entidade — `src/app/domain/entities/refresh_token.py`

```python
@dataclass
class RefreshToken:
    id: UUID
    usuario_id: UUID
    token_hash: str
    familia_id: UUID
    criado_em: datetime
    expira_em: datetime
    revogado_em: datetime | None = None

    def esta_expirado(self, agora: datetime) -> bool: ...
    def esta_revogado(self) -> bool: ...
    def revogar(self, agora: datetime) -> None: ...
```

### Tabela `refresh_tokens` — `src/app/db/models/refresh_token.py` + migration

| Coluna | Tipo | Restrição |
|---|---|---|
| `id` | UUID | PK |
| `usuario_id` | UUID | FK `usuarios.id`, `ON DELETE CASCADE` |
| `token_hash` | `String(64)` | unique, não nulo |
| `familia_id` | UUID | indexado, não nulo |
| `criado_em` | `DateTime(timezone=True)` | não nulo |
| `expira_em` | `DateTime(timezone=True)` | não nulo |
| `revogado_em` | `DateTime(timezone=True)` | nulo |

Migration `cria_tabela_refresh_tokens` com `down_revision = "c9e3a5b7d1f2"` (head atual). `downgrade` remove a tabela.

### Repositório

ABC em `src/app/repositories/interfaces/refresh_token_repository.py`, implementação em `src/app/repositories/sqlalchemy/refresh_token_repository.py` e `FakeRefreshTokenRepository` em `tests/fixtures/`, seguindo o padrão dos repositórios existentes (a implementação SQLAlchemy faz o próprio commit):

```python
class RefreshTokenRepository(ABC):
    def salvar(self, token: RefreshToken) -> None: ...
    def buscar_por_hash(self, token_hash: str) -> RefreshToken | None: ...
    def revogar_familia(self, familia_id: UUID, revogado_em: datetime) -> None: ...
```

`revogar_familia` só marca tokens da família que ainda estão com `revogado_em` nulo.

### Serviço — `src/app/services/refresh_token_service.py`

```python
@dataclass
class ParTokens:
    access_token: str
    refresh_token: str
    expires_in: int

class RefreshTokenService:
    def __init__(
        self,
        refresh_token_repository: RefreshTokenRepository,
        usuario_repository: UsuarioRepository,
        jwt_secret_key: str,
        access_expiracao_minutos: int,
        refresh_expiracao_dias: int,
        agora: Callable[[], datetime] = lambda: datetime.now(UTC),
    ): ...

    def emitir(self, usuario_id: UUID) -> ParTokens: ...
    def renovar(self, refresh_token: str) -> ParTokens: ...
    def revogar(self, refresh_token: str) -> None: ...
```

- `emitir`: cria uma família nova, grava o hash do refresh e devolve o par. `expires_in = access_expiracao_minutos * 60`.
- `renovar`:
  - hash não encontrado → `RefreshTokenInvalidoError`;
  - token já revogado (reuso) → `revogar_familia` e depois `RefreshTokenInvalidoError`;
  - token expirado → `RefreshTokenInvalidoError`;
  - usuário inexistente ou com `ativo=False` → `RefreshTokenInvalidoError`;
  - caso válido → revoga o token atual, emite um novo refresh na mesma família e um novo access token.
- `revogar`: se o hash existe, revoga a família; se não existe, não faz nada (logout idempotente).
- Access token continua vindo de `core/security.criar_token`.

`RefreshTokenInvalidoError` fica em `src/app/services/exceptions.py`.

### API

- `TokenResponse` passa a ser `{access_token, refresh_token, token_type="bearer", expires_in}`.
- `POST /api/v1/usuarios` e `POST /api/v1/auth/login` usam `RefreshTokenService.emitir`.
- `POST /api/v1/auth/refresh` com corpo `{"refresh_token": "..."}` → 200 com `TokenResponse`; `RefreshTokenInvalidoError` → 401 `"Refresh token invalido"`.
- `POST /api/v1/auth/logout` com corpo `{"refresh_token": "..."}` → 204, sem exigir access token (o cliente pode estar com o access expirado).
- `deps.py`: `get_refresh_token_repository` e `get_refresh_token_service`.
- Configuração: `jwt_expiration_minutes` padrão passa para 30; novo `refresh_token_expiracao_dias: int = 30`; `.env.example` atualizado.

## Testes

- **Entidade:** expiração e revogação.
- **Serviço** (Fake + relógio fixo):
  - `emitir` grava só o hash (o token em texto não aparece no repositório) e o access token decodifica para o usuário;
  - `renovar` revoga o token usado, cria outro na mesma família e devolve tokens novos;
  - token expirado, inexistente, usuário inativo → erro;
  - reuso de token revogado revoga a família: o token emitido na rotação também deixa de funcionar;
  - `revogar` revoga a família; token desconhecido não lança erro.
- **Controllers:** cadastro e login devolvem `refresh_token` e `expires_in`; `/auth/refresh` 200 e depois 401 no reuso; `/auth/logout` 204 e o refresh seguinte 401; corpo sem `refresh_token` → 422.
- **Integração** (`-m integration`, Postgres): salvar, buscar por hash, `revogar_familia` só afeta a família informada, `token_hash` duplicado viola a restrição unique.
- **Migration:** `alembic upgrade head` e `alembic downgrade -1` contra um Postgres descartável na porta 5434.

## Riscos

- **Clientes que guardam só o access token** passam a ser deslogados a cada 30 minutos até implementarem o refresh. O valor é configurável; durante a transição dá para manter `JWT_EXPIRATION_MINUTES` mais alto no ambiente.
- **Renovações concorrentes** (duas abas usando o mesmo refresh ao mesmo tempo): a segunda é tratada como reuso e derruba a família. É o comportamento esperado da rotação; os clientes devem serializar o refresh.
