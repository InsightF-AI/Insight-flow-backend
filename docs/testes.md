# Estratégia de testes — API

A pirâmide tem três andares. **Base (652 testes de unidade):** domínio, serviços, IA, scheduler, notificações e clientes externos, sem rede e sem banco — 20 dublês em memória implementam as mesmas interfaces dos repositórios, e `httpx.MockTransport` responde no lugar de brapi, Binance, BCB, Expo e Web Push. **Meio (139 testes de contrato HTTP):** os endpoints FastAPI chamados de verdade pelo `TestClient`, com `dependency_overrides` trocando as dependências reais pelos dublês — conferem status, JSON, autenticação e erro. **Topo (92 testes de integração):** repositórios em PostgreSQL 16 real e cache e barramento em Redis 7 real, subidos pelo próprio GitHub Actions; cada teste roda numa transação desfeita no fim, então um não suja o outro.

Cobertura da V0: autenticação com refresh e logout, watchlist, ativos (busca, cotação, histórico, indicadores), sinais e backtest, alertas, carteira e operações, notificações por WebSocket, push Expo e Web Push, análise por IA e chat, além do scheduler e dos limites de requisição das integrações.

Fica para depois: teste de carga, teste de contrato publicado para os clientes (web, desktop e mobile) e cobertura de código publicada no pipeline.

TDD é o ciclo vermelho, verde, refatora: primeiro o teste que falha, depois o código mínimo que o faz passar, e só então a melhoria do desenho. Seis dos oito planos de implementação do projeto abrem a tarefa escrevendo os testes que falham.

São **883 testes** em 105 arquivos, verdes no CI a cada push e pull request (`883 passed in 70.67s`). Rodar: `pytest -q`; só o que não precisa de infraestrutura: `pytest -q tests/unit`.
