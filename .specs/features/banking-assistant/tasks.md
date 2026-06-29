# Tasks: Banking Assistant

## Tarefas

- `TASK-001` Criar estrutura do projeto, configuração, `.env.example` e dados CSV de exemplo.
  - Verificação: arquivos existem e documentam as variáveis obrigatórias.

- `TASK-002` Implementar autenticação via CSV.
  - Requisitos: `REQ-001`, `REQ-002`.
  - Verificação: testes de sucesso e falha de autenticação passam, incluindo o limite de três tentativas.

- `TASK-003` Implementar regras de crédito, extração de valor por LLM e registro de solicitação.
  - Requisitos: `REQ-004`, `REQ-005`, `REQ-005A`, `REQ-006`, `REQ-007`, `REQ-007A`.
  - Verificação: testes cobrem aprovação, rejeição, escrita no CSV, extração por LLM e fallback, oferta de entrevista com consentimento e ausência de re-submissão duplicada.

- `TASK-004` Implementar entrevista passo a passo e cálculo de score.
  - Requisitos: `REQ-008`, `REQ-009`.
  - Verificação: testes cobrem coleta campo a campo, conclusão, cálculo e atualização de `clientes.csv`.

- `TASK-005` Implementar câmbio como subgrafo com *function tool* e encerramento amigável.
  - Requisitos: `REQ-010`, `REQ-012`.
  - Verificação: testes cobrem o tool-calling, o fallback determinístico de moeda, a tradução para pt-BR, o uso de cliente fake e a ausência de `TAVILY_API_KEY`.

- `TASK-006` Implementar grafo LangGraph, memória de fluxo e UI Streamlit.
  - Requisitos: `REQ-003`, `REQ-003A`, `REQ-003B`, `REQ-003C`, `REQ-003D`, `REQ-011`, `REQ-012`, `REQ-016`, `REQ-017`, `REQ-018`, `REQ-019`, `REQ-020`.
  - Verificação: testes de roteamento e memória de fluxo passam, escape de cifrão validado, cache do client LLM testado e integração end-to-end via `build_graph().invoke()`.

- `TASK-007` Implementar observabilidade e evals com LangSmith.
  - Requisitos: `REQ-013`, `REQ-014`, `REQ-015`.
  - Verificação: testes cobrem mascaramento de CPF, metadados de trace e métrica `intent_accuracy`.

- `TASK-008` Escrever README alinhado às seções obrigatórias do desafio.
  - Verificação: README contém visão geral, arquitetura (agentes/fluxos/dados), funcionalidades, desafios, escolhas técnicas e tutorial de execução e testes.
