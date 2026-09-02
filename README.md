# Insight Flow — Backend

Sistema de Análise de Ativos do Mercado Financeiro — serviço backend centralizado (API REST + Scheduler + camada de IA) consumido pelos clientes web, mobile e desktop.

## Estrutura do projeto

```
src/app/
├── api/v1/
│   ├── controllers/     # Endpoints FastAPI (camada de apresentação)
│   └── schemas/         # DTOs Pydantic de request/response
├── core/                 # Configuração, segurança (JWT/bcrypt), logging, exceptions
├── domain/
│   ├── entities/         # Entidades de domínio (Usuario, Ativo, Cotacao, ...)
│   ├── enums/            # Enumerações de domínio (TipoAtivo, TipoIndicador, ...)
│   └── value_objects/    # Objetos de valor sem persistência (ResultadoBacktest, Posicao, ...)
├── repositories/
│   ├── interfaces/       # Contratos de persistência (inversão de dependência)
│   └── sqlalchemy/       # Implementações concretas com SQLAlchemy
├── services/              # Regras de negócio e orquestração
├── integrations/          # Adaptadores para APIs externas (brapi, Binance, BCB)
├── ai/
│   ├── providers/         # Abstração de provedores de LLM (Claude, OpenAI, Ollama)
│   ├── prompts/           # Templates de prompt versionados
│   └── guardrails/        # Validador determinístico de saída da IA
├── scheduler/
│   └── jobs/               # Rotinas periódicas (APScheduler)
├── notifications/          # Envio de alertas (web push, mobile, desktop)
└── db/
    └── models/              # Modelos ORM (SQLAlchemy)

alembic/          # Migrações de banco de dados
tests/
├── unit/
├── integration/
└── fixtures/
```

## Stack

Python 3.11+, FastAPI, SQLAlchemy, PostgreSQL, Redis, Pydantic, APScheduler, pandas-ta.

Ver `documentacao-tecnica-v1.1.docx` e `escopo-e-stack-v1.1.docx` para especificação completa.
