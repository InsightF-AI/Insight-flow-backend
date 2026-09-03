# Guia de Contribuicao - InsightFlow AI

## Modelo de Branches (Git Flow)

Adotamos o modelo **Git Flow** para organizar o desenvolvimento:

| Branch        | Papel                                                        |
|---------------|-------------------------------------------------------------|
| `main`        | Codigo estavel, em producao. Cada merge gera uma versao.    |
| `develop`     | Integracao das proximas funcionalidades.                    |
| `feature/*`   | Novas funcionalidades. Nascem de `develop` e voltam a ela.  |
| `release/*`   | Preparacao de uma nova versao (ajustes finais, versao).     |
| `hotfix/*`    | Correcoes urgentes em producao. Nascem de `main`.           |

### Fluxo de uma funcionalidade

```bash
# a partir da develop atualizada
git checkout develop
git pull origin develop

# cria a branch de feature
git checkout -b feature/cadastro-watchlist

# ... desenvolve, commita ...
git add .
git commit -m "feat: adiciona endpoint de watchlist"
git push origin feature/cadastro-watchlist

# abre um Pull Request de feature/cadastro-watchlist -> develop
```

### Preparando uma release

```bash
git checkout -b release/0.2.0 develop
# ajustes finais + numero de versao
git checkout main && git merge --no-ff release/0.2.0
git tag -a v0.2.0 -m "Versao 0.2.0"
git checkout develop && git merge --no-ff release/0.2.0
git push origin main develop --tags
```

## Padrao de Commits (Conventional Commits)

- `feat:` nova funcionalidade
- `fix:` correcao de bug
- `docs:` documentacao
- `refactor:` refatoracao sem mudanca de comportamento
- `test:` testes
- `chore:` tarefas de manutencao

## Regras de Pull Request

1. Todo merge em `main` e `develop` passa por Pull Request.
2. O PR so pode ser mesclado com o CI verde (lint + testes).
3. E necessaria a aprovacao de ao menos 1 revisor.
4. Alteracoes em areas com dono no CODEOWNERS exigem a aprovacao do dono.
