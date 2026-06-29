# Feature: Banking Assistant

## Requisitos

- `REQ-001` O sistema deve autenticar o cliente por CPF e data de nascimento usando `data/clientes.csv`, aceitando datas em formato ISO (`AAAA-MM-DD`) e brasileiro (`DD/MM/AAAA` ou `DD-MM-AAAA`).
- `REQ-002` O sistema deve permitir até três falhas consecutivas de autenticação antes de encerrar o atendimento.
- `REQ-003` O sistema deve classificar a intenção do cliente apenas após autenticação bem-sucedida.
- `REQ-003A` Quando `OPENROUTER_API_KEY` estiver configurada, a classificação de intenção deve usar DeepSeek via OpenRouter como caminho principal.
- `REQ-003B` A classificação de intenção deve retornar JSON estruturado com `intent` e `confidence`, validado por `IntentResult`, usando as categorias `credit`, `credit_interview`, `exchange`, `end` ou `unknown`.
- `REQ-003C` O fallback determinístico por palavras-chave deve ser usado somente quando não houver LLM configurado ou quando ocorrer falha técnica na chamada ao provedor.
- `REQ-003D` Quando o LLM retornar `unknown`, o sistema deve respeitar essa decisão e pedir esclarecimento ao cliente, sem sobrescrever a resposta com fallback determinístico.
- `REQ-004` O sistema deve consultar o limite de crédito atual do cliente autenticado.
- `REQ-005` O sistema deve registrar solicitações de aumento de limite em `data/solicitacoes_aumento_limite.csv`.
- `REQ-005A` O valor de limite desejado deve ser extraído pelo LLM (entendendo "cinco mil", "5k", "8 mil"), validado por `LimitIncreaseRequest`, com fallback determinístico.
- `REQ-006` O sistema deve aprovar ou rejeitar aumento de limite comparando o score atual com `data/score_limite.csv`.
- `REQ-007` Quando o aumento for rejeitado, o sistema deve oferecer a entrevista de crédito e só conduzi-la se o cliente aceitar; se recusar, encerrar de forma cordial ou oferecer outro assunto.
- `REQ-007A` Quando o limite máximo permitido pelo score for menor ou igual ao limite atual, o sistema deve explicar e oferecer a entrevista, sem pedir um valor.
- `REQ-008` O sistema deve conduzir a entrevista passo a passo, extraindo cada campo via LLM (validado por `CreditInterviewAnswers`, com fallback) e recalcular o score com base em renda, emprego, despesas, dependentes e dívidas.
- `REQ-009` O sistema deve atualizar o score em `data/clientes.csv` após entrevista concluída e retornar para nova análise de crédito.
- `REQ-010` O sistema deve consultar a cotação de qualquer moeda via *function tool* (LLM com `bind_tools` decide a moeda; Tavily como backend determinístico), apresentar a resposta em português e encerrar o tópico de câmbio com uma mensagem amigável.
- `REQ-011` O sistema deve encerrar o atendimento quando o cliente solicitar fim da conversa.
- `REQ-012` O sistema deve tratar entradas inválidas, CSV ausente e falha de API com mensagens controladas.
- `REQ-013` O sistema deve registrar traces de atendimento no LangSmith quando `LANGSMITH_TRACING=true`.
- `REQ-014` Traces e metadados não devem expor CPF completo; identificadores sensíveis devem ser mascarados.
- `REQ-015` O projeto deve incluir uma avaliação offline de classificação de intenção com dataset pequeno e métrica `intent_accuracy`.
- `REQ-016` Respostas geradas por LLM devem ser normalizadas para texto simples antes de aparecerem na UI, evitando Markdown, listas ou formatações inconsistentes no Streamlit.
- `REQ-017` O sistema deve manter memória de fluxo ativo (`active_flow`) para continuar fluxos pendentes (aumento, oferta de entrevista, entrevista) sem reclassificar a intenção do zero.
- `REQ-018` O client LLM deve ser reutilizado em cache por modelo e temperatura para reduzir latência entre turnos.
- `REQ-019` Mensagens exibidas na UI devem escapar o cifrão para evitar que o Streamlit renderize "R$" como fórmula LaTeX.
- `REQ-020` Erros técnicos (CSV, API, validação) devem ser registrados via logging sem expor dados sensíveis, mantendo a conversa fluindo.

## Fora de Escopo

- Integração bancária real.
- Persistência em banco de dados relacional.
- Deploy em nuvem.
- Análise de crédito baseada em modelo estatístico real.
