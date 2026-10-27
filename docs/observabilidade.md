# Observabilidade, monitoramento e auditoria

O Insight Flow é monitorado no **Grafana Cloud (plano grátis)**. Cada máquina (homologação na VM
da Azure e produção na VPS da Hostinger) roda um único agente, o **Grafana Alloy**, que coleta
métricas e logs e os envia para a nuvem. Nada de Grafana, Prometheus ou Loki roda nas nossas
máquinas: o monitoramento continua de pé mesmo se a VPS cair, e não há painel novo exposto na
internet para proteger.

```
 VM / VPS ─────────────────────────────────────────────┐
 │ backend :9100/metrics ──┐                           │
 │ postgres ───────────────┤                           │        Grafana Cloud
 │ redis ──────────────────┼──> Alloy ──── HTTPS ──────┼──> Prometheus (métricas)
 │ máquina e containers ───┤                           │    Loki (logs)
 │ logs insightflow-* ─────┘                           │    Grafana (dashboards e alertas)
 └─────────────────────────────────────────────────────┘    Synthetic Monitoring (uptime)
```

## O que é coletado

| Sinal | Origem | Para quê |
|---|---|---|
| Requisições, status e latência por rota | `/metrics` da API na porta interna 9100 | tráfego, taxa de erro, p95 |
| Execuções e falhas dos jobs | mesmo `/metrics` | saber se o scheduler parou ou está falhando |
| CPU, memória, disco e rede da máquina | exporter `unix` do Alloy | capacidade da VM/VPS |
| CPU e memória por container `insightflow-*` | cAdvisor embutido no Alloy | qual serviço está consumindo |
| PostgreSQL e Redis | exporters `postgres` e `redis` do Alloy | banco e cache no ar, conexões, memória |
| Logs de todos os containers `insightflow-*` | Docker, pelo Alloy | busca centralizada, com o `nivel` da API como rótulo |
| Disponibilidade externa | Synthetic Monitoring do Grafana Cloud | a API e o web respondem da internet? |

As rotas entram nas métricas pelo **template** (`/api/v1/ativos/{ticker}`), nunca pelo caminho
com o ticker, para o número de séries não crescer sem limite. Caminho inexistente vira
`nao_mapeada`. O `/health` fica fora.

A porta 9100 só existe na rede interna do compose: o Traefik encaminha apenas a 8000.

## Auditoria

São três camadas, ligadas pelo `correlation_id` (o mesmo valor do header `X-Request-ID`):

1. **Log de cada requisição** (API): método, rota, status, duração, `usuario_id`, IP do cliente e
   `correlation_id`, em JSON.
2. **Eventos de segurança** (API): `login_aceito`, `login_recusado`, `logout`,
   `refresh_invalido`, `refresh_reutilizado`, `recuperacao_senha`, `senha_alterada` e
   `senha_redefinida`.
3. **Trilha no banco** (PostgreSQL): triggers gravam na tabela `auditoria` todo INSERT, UPDATE e
   DELETE em `usuarios`, `refresh_tokens`, `operacoes`, `watchlists`, `alertas_personalizados`,
   `dispositivos_push` e `inscricoes_web_push`, com o estado antes e depois. Senhas, hashes de
   token e credenciais de push são removidos antes de gravar. Cada linha também sai no log do
   Postgres (`auditoria tabela=... correlation_id=...`), sem os dados, para aparecer no Grafana.

Por ser feita por trigger, a trilha do banco pega qualquer alteração, inclusive as feitas fora
da API (um `psql` na mão, por exemplo). Nesse caso a coluna `usuario_banco` mostra quem foi e o
`correlation_id` fica vazio.

O Postgres também registra conexões e desconexões, todo comando DDL (`CREATE`, `ALTER`, `DROP`),
queries acima de 1 segundo, esperas por lock e falhas de autenticação.

### Consultas úteis (na máquina)

```bash
docker exec -it insightflow-postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

```sql
-- O que aconteceu com os dados de um usuário
SELECT ocorrido_em, tabela, operacao, dados_antes, dados_depois
FROM auditoria WHERE usuario_id = '<uuid>' ORDER BY ocorrido_em DESC LIMIT 50;

-- Tudo o que uma requisição alterou (o correlation_id vem do log da API ou do X-Request-ID)
SELECT * FROM auditoria WHERE correlation_id = '<id>';

-- Alterações feitas fora da API
SELECT ocorrido_em, usuario_banco, tabela, operacao, registro_id
FROM auditoria WHERE correlation_id IS NULL ORDER BY ocorrido_em DESC LIMIT 50;
```

## Configurar (uma vez)

### 1. Conta e credenciais

1. Crie a conta grátis em [grafana.com](https://grafana.com/auth/sign-up/create-user) e um stack
   (escolha a região mais próxima).
2. Em **My Account → Stack → Prometheus → Details**, anote a URL de *Remote Write* e o
   *Username* (número).
3. Em **Loki → Details**, anote a URL (termina em `/loki/api/v1/push`) e o *User* (número).
4. Em **Access Policies**, crie uma política com os escopos `metrics:write` e `logs:write` e gere
   um token.

### 2. `.env` de cada máquina

Acrescente ao `.env` de `~/apps/insightflow/backend` na VM e na VPS:

```bash
GRAFANA_CLOUD_PROMETHEUS_URL=https://prometheus-prod-XX-....grafana.net/api/prom/push
GRAFANA_CLOUD_PROMETHEUS_USUARIO=1234567
GRAFANA_CLOUD_LOKI_URL=https://logs-prod-XXX.grafana.net/loki/api/v1/push
GRAFANA_CLOUD_LOKI_USUARIO=7654321
GRAFANA_CLOUD_TOKEN=glc_...
```

O compose monta a conexão do exporter do Postgres a partir de `POSTGRES_USER`,
`POSTGRES_PASSWORD` e `POSTGRES_DB`, que já estão no `.env`. Se a senha tiver caracteres
especiais de URL (`@`, `/`, `:`, `#`), troque por uma sem eles.

O CD só sobe o Alloy quando encontra `GRAFANA_CLOUD_TOKEN` no `.env`. Até lá o deploy segue
normal e só avisa no log. Depois de preencher, rode o próximo deploy ou, na máquina:

```bash
cd ~/apps/insightflow/backend && docker compose up -d alloy && docker logs -f insightflow-alloy
```

### 3. Dashboard

Em **Dashboards → New → Import**, envie
[`deploy/observabilidade/dashboards/insightflow-visao-geral.json`](../deploy/observabilidade/dashboards/insightflow-visao-geral.json)
e escolha as fontes `grafanacloud-...-prom` e `grafanacloud-...-logs`. O seletor **Ambiente**
alterna entre homologação e produção.

### 4. Disponibilidade (Synthetic Monitoring)

Em **Testing & synthetics → Synthetics → Add check → HTTP**, crie as quatro checagens, cada uma
a partir de duas sondas (por exemplo, São Paulo e Virgínia), a cada 1 minuto:

| Nome | URL |
|---|---|
| API produção | `https://api-insight.agilesoftware.net.br/health` |
| Web produção | `https://insight.agilesoftware.net.br/healthz` |
| API homologação | `https://hom-api-insight.agilesoftware.net.br/health` |
| Web homologação | `https://hom-insight.agilesoftware.net.br/healthz` |

Ative **Alerting → Sensitivity: Medium** em cada uma. O Synthetics também acompanha a validade do
certificado TLS.

### 5. Alertas

Em **Alerting → Contact points**, cadastre o e-mail da equipe (e, quando o relay estiver pronto,
um *webhook* para ele). Depois, em **Alert rules → New alert rule**:

| Alerta | Consulta | Condição |
|---|---|---|
| API fora do ar | `max by (ambiente) (up{job="insightflow-api"})` | `< 1` por 2 min |
| Agente sem dados | `count by (ambiente) (up{job="maquina"})` | sem dados por 5 min |
| Erros 5xx | `sum by (ambiente) (rate(insightflow_http_requisicoes_total{status=~"5.."}[5m])) / sum by (ambiente) (rate(insightflow_http_requisicoes_total[5m]))` | `> 0.05` por 5 min |
| API lenta | `histogram_quantile(0.95, sum by (le, ambiente) (rate(insightflow_http_duracao_segundos_bucket[5m])))` | `> 2` por 10 min |
| Job falhou | `sum by (ambiente, job) (increase(insightflow_job_execucoes_total{resultado="falha"}[15m]))` | `> 0` |
| Banco fora do ar | `max by (ambiente) (pg_up)` | `< 1` por 2 min |
| Disco cheio | `1 - max by (ambiente) (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"})` | `> 0.85` por 10 min |
| Memória alta | `1 - avg by (ambiente) (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)` | `> 0.9` por 10 min |
| Força bruta no login (Loki) | `sum by (ambiente) (count_over_time({container="insightflow-backend"} \| json \| evento="login_recusado" [5m]))` | `> 20` |

## Limites do plano grátis

10 mil séries de métricas, 50 GB de logs por mês e 14 dias de retenção. A coleta já foi
recortada para caber com folga: o cAdvisor só envia oito métricas e só dos containers
`insightflow-*`, e a máquina, o banco e o cache são lidos a cada 60 segundos. A tabela
`auditoria` fica no nosso Postgres, sem limite de retenção.

## Verificações rápidas

```bash
# Na máquina: a API expõe as métricas na porta interna
docker exec insightflow-backend python -c "import urllib.request as u; print(u.urlopen('http://localhost:9100/metrics').read().decode())" | grep insightflow_http
# Por fora, a porta não existe (deve falhar)
curl -m 5 https://api-insight.agilesoftware.net.br:9100/metrics
# O agente está enviando (erros de autenticação ou de URL aparecem aqui)
docker logs --tail 50 insightflow-alloy
```

No Grafana, **Explore → Loki** com `{container="insightflow-backend"} | json` mostra os logs da
API. Clique num `correlation_id` para seguir uma requisição de ponta a ponta.
