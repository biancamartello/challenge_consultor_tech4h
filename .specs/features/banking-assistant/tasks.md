# Tasks: Banking Assistant

## Tarefas

- `TASK-001` Criar estrutura do projeto, configuracao, `.env.example` e dados CSV de exemplo.
  - Verificacao: arquivos existem e documentam as variaveis obrigatorias.

- `TASK-002` Implementar autenticacao via CSV.
  - Requisitos: `REQ-001`, `REQ-002`.
  - Verificacao: testes de sucesso e falha de autenticacao passam.

- `TASK-003` Implementar regras de credito, extracao de valor por LLM e registro de solicitacao.
  - Requisitos: `REQ-004`, `REQ-005`, `REQ-005A`, `REQ-006`, `REQ-007`, `REQ-007A`.
  - Verificacao: testes cobrem aprovacao, rejeicao, escrita no CSV, extracao por LLM e fallback, e oferta de entrevista com consentimento.

- `TASK-004` Implementar entrevista passo a passo e calculo de score.
  - Requisitos: `REQ-008`, `REQ-009`.
  - Verificacao: testes cobrem coleta campo a campo, conclusao, calculo e atualizacao de `clientes.csv`.

- `TASK-005` Implementar cambio via Tavily com encerramento amigavel.
  - Requisitos: `REQ-010`, `REQ-012`.
  - Verificacao: teste usa cliente fake e cobre ausencia de `TAVILY_API_KEY`.

- `TASK-006` Implementar grafo LangGraph, memoria de fluxo e UI Streamlit.
  - Requisitos: `REQ-003`, `REQ-003A`, `REQ-003B`, `REQ-003C`, `REQ-003D`, `REQ-011`, `REQ-012`, `REQ-016`, `REQ-017`, `REQ-018`, `REQ-019`, `REQ-020`.
  - Verificacao: testes de roteamento e memoria de fluxo passam, escape de cifrao validado, cache do client LLM testado.

- `TASK-007` Implementar observabilidade e evals com LangSmith.
  - Requisitos: `REQ-013`, `REQ-014`, `REQ-015`.
  - Verificacao: testes cobrem mascaramento de CPF, metadados de trace e metrica `intent_accuracy`.

- `TASK-008` Escrever README alinhado as secoes obrigatorias do desafio.
  - Verificacao: README contem visao geral, arquitetura (agentes/fluxos/dados), funcionalidades, desafios, escolhas tecnicas e tutorial de execucao e testes.
