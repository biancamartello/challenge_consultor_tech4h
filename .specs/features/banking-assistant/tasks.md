# Tasks: Banking Assistant

## Tarefas

- `TASK-001` Criar estrutura do projeto, configuracao, `.env.example` e dados CSV de exemplo.
  - Verificacao: arquivos existem e documentam as variaveis obrigatorias.

- `TASK-002` Implementar autenticacao via CSV.
  - Requisitos: `REQ-001`, `REQ-002`.
  - Verificacao: testes de sucesso e falha de autenticacao passam.

- `TASK-003` Implementar regras de credito e registro de solicitacao.
  - Requisitos: `REQ-004`, `REQ-005`, `REQ-006`, `REQ-007`.
  - Verificacao: testes cobrem aprovacao, rejeicao e escrita no CSV.

- `TASK-004` Implementar entrevista e calculo de score.
  - Requisitos: `REQ-008`, `REQ-009`.
  - Verificacao: testes cobrem calculo e atualizacao de `clientes.csv`.

- `TASK-005` Implementar cambio via Tavily.
  - Requisitos: `REQ-010`, `REQ-012`.
  - Verificacao: teste usa cliente fake e cobre ausencia de `TAVILY_API_KEY`.

- `TASK-006` Implementar grafo LangGraph e UI Streamlit.
  - Requisitos: `REQ-003`, `REQ-003A`, `REQ-003B`, `REQ-003C`, `REQ-003D`, `REQ-011`, `REQ-012`.
  - Verificacao: testes de roteamento passam, incluindo classificacao por LLM estruturado, respeito ao `unknown` do LLM e fallback deterministico apenas sem LLM ou em falha tecnica.

- `TASK-007` Implementar observabilidade e evals com LangSmith.
  - Requisitos: `REQ-013`, `REQ-014`, `REQ-015`.
  - Verificacao: testes cobrem mascaramento de CPF, metadados de trace e metrica `intent_accuracy`.

- `TASK-008` Escrever README final.
  - Verificacao: README contem visao geral, arquitetura, funcionalidades, escolhas tecnicas e execucao.
