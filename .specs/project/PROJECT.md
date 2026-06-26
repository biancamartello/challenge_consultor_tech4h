# Desafio Agentes IA Banco Agil

## Visao

Construir um atendimento bancario inteligente para o Banco Agil, com uma experiencia unica para o cliente e capacidades especializadas para autenticacao, credito, entrevista de credito e cambio.

## Objetivos

- Entregar uma UI simples em Streamlit para simular um atendimento completo.
- Usar LangGraph para orquestrar o fluxo conversacional e as transicoes.
- Usar DeepSeek via OpenRouter como classificador principal de intencao e apoio conversacional.
- Usar Tavily para consulta de cambio em tempo real.
- Usar LangSmith para observabilidade leve e eval offline da classificacao de intencao.
- Manter regras bancarias em Python, com funcoes testaveis e auditaveis.

## Criterios de Sucesso

- O cliente nao percebe troca entre agentes internos.
- Autenticacao via `clientes.csv` respeita limite de tres tentativas.
- A triagem de intencao e feita pelo LLM com saida estruturada, quando `OPENROUTER_API_KEY` estiver configurada.
- Fallback deterministico de intencao existe apenas para ambiente sem LLM ou falha tecnica do provedor.
- Traces do atendimento sao registrados no LangSmith com CPF mascarado.
- Eval offline mede acuracia da classificacao de intencao em um dataset pequeno.
- Solicitacoes de aumento de limite sao registradas em CSV.
- Score de credito e limite sao decididos por regra deterministica.
- Entrevista recalcula score e retorna para nova analise de credito.
- Cambio consulta Tavily e falha de forma controlada quando a API estiver indisponivel.
