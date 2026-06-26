# Feature: Banking Assistant

## Requisitos

- `REQ-001` O sistema deve autenticar o cliente por CPF e data de nascimento usando `data/clientes.csv`.
- `REQ-002` O sistema deve permitir ate tres falhas consecutivas de autenticacao antes de encerrar o atendimento.
- `REQ-003` O sistema deve classificar a intencao do cliente apenas apos autenticacao bem-sucedida.
- `REQ-003A` Quando `OPENROUTER_API_KEY` estiver configurada, a classificacao de intencao deve usar DeepSeek via OpenRouter como caminho principal.
- `REQ-003B` A classificacao de intencao deve retornar JSON estruturado com `intent` e `confidence`, validado por `IntentResult`, usando as categorias `credit`, `credit_interview`, `exchange`, `end` ou `unknown`.
- `REQ-003C` O fallback deterministico por palavras-chave deve ser usado somente quando nao houver LLM configurado ou quando ocorrer falha tecnica na chamada ao provedor.
- `REQ-003D` Quando o LLM retornar `unknown`, o sistema deve respeitar essa decisao e pedir esclarecimento ao cliente, sem sobrescrever a resposta com fallback deterministico.
- `REQ-004` O sistema deve consultar o limite de credito atual do cliente autenticado.
- `REQ-005` O sistema deve registrar solicitacoes de aumento de limite em `data/solicitacoes_aumento_limite.csv`.
- `REQ-006` O sistema deve aprovar ou rejeitar aumento de limite comparando o score atual com `data/score_limite.csv`.
- `REQ-007` O sistema deve oferecer entrevista de credito quando uma solicitacao de aumento for rejeitada.
- `REQ-008` O sistema deve recalcular o score com base em renda, emprego, despesas, dependentes e dividas.
- `REQ-009` O sistema deve atualizar o score em `data/clientes.csv` apos entrevista concluida.
- `REQ-010` O sistema deve consultar cotacao de moedas via Tavily.
- `REQ-011` O sistema deve encerrar o atendimento quando o cliente solicitar fim da conversa.
- `REQ-012` O sistema deve tratar entradas invalidas, CSV ausente e falha de API com mensagens controladas.
- `REQ-013` O sistema deve registrar traces de atendimento no LangSmith quando `LANGSMITH_TRACING=true`.
- `REQ-014` Traces e metadados nao devem expor CPF completo; identificadores sensiveis devem ser mascarados.
- `REQ-015` O projeto deve incluir uma avaliacao offline de classificacao de intencao com dataset pequeno e metrica `intent_accuracy`.

## Fora de Escopo

- Integracao bancaria real.
- Persistencia em banco de dados relacional.
- Deploy em nuvem.
- Analise de credito baseada em modelo estatistico real.
