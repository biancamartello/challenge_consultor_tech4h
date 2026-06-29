# Desafio Agentes IA Banco Ágil

## Visão

Construir um atendimento bancário inteligente para o Banco Ágil, com uma experiência única para o cliente e capacidades especializadas para autenticação, crédito, entrevista de crédito e câmbio.

## Objetivos

- Entregar uma UI simples em Streamlit para simular um atendimento completo.
- Usar LangGraph para orquestrar o fluxo conversacional e as transições.
- Usar DeepSeek via OpenRouter como classificador principal de intenção e apoio conversacional.
- Usar Tavily para consulta de câmbio em tempo real, acionada por uma *function tool*.
- Usar LangSmith para observabilidade leve e eval offline da classificação de intenção.
- Manter regras bancárias em Python, com funções testáveis e auditáveis.

## Critérios de Sucesso

- O cliente não percebe troca entre agentes internos.
- Autenticação via `clientes.csv` respeita o limite de três tentativas.
- A triagem de intenção é feita pelo LLM com saída estruturada, quando `OPENROUTER_API_KEY` estiver configurada.
- Fallback determinístico de intenção existe apenas para ambiente sem LLM ou falha técnica do provedor.
- Traces do atendimento são registrados no LangSmith com CPF mascarado.
- Eval offline mede acurácia da classificação de intenção em um dataset pequeno.
- Solicitações de aumento de limite são registradas em CSV.
- Score de crédito e limite são decididos por regra determinística.
- Entrevista recalcula score e retorna para nova análise de crédito.
- Câmbio consulta a Tavily e falha de forma controlada quando a API estiver indisponível.
