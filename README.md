# Desafio Agentes IA Banco Agil

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-agentic_workflow-1C3C3C)](https://www.langchain.com/langgraph)
[![LangSmith](https://img.shields.io/badge/LangSmith-observability_&_evals-1C3C3C)](https://www.langchain.com/langsmith)
[![Streamlit](https://img.shields.io/badge/Streamlit-chat_UI-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Tests](https://img.shields.io/badge/tests-23_passed-brightgreen)](#testes)

**Tags:** `langgraph` `langsmith` `openrouter` `deepseek` `streamlit` `tavily` `ai-agents` `sdd` `evals`

Solucao para o desafio tecnico de agentes de IA do Banco Agil. O projeto implementa um atendimento bancario inteligente com experiencia unificada para o cliente e capacidades internas para autenticacao, credito, entrevista de credito, cambio, observabilidade e avaliacao.

> Enunciado original: [`docs/challenge/desafio-tecnico-agentes-ia-bianca.pdf`](docs/challenge/desafio-tecnico-agentes-ia-bianca.pdf)

## Sumario

- [Visao Geral](#visao-geral)
- [Arquitetura](#arquitetura)
- [Funcionalidades](#funcionalidades)
- [Observabilidade e Evals](#observabilidade-e-evals)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Como Executar](#como-executar)
- [Testes](#testes)
- [Decisoes Tecnicas](#decisoes-tecnicas)

## Visao Geral

A proposta do desafio descreve agentes especializados, mas tambem exige que as transicoes sejam implicitas para o cliente. Por isso, a solucao usa um unico `BankingAssistantGraph` em LangGraph, no qual cada agente do enunciado vira uma capacidade interna do grafo.

Essa decisao evita quatro bots soltos e mostra separacao de responsabilidades sem comprometer a experiencia conversacional.

## Arquitetura

```mermaid
flowchart TD
    user["Cliente"] --> ui["Streamlit Chat"]
    ui --> graph["BankingAssistantGraph"]
    graph --> triage["triage: autenticar e rotear"]
    triage -->|"credito"| credit["credit: limite e aumento"]
    triage -->|"entrevista"| interview["credit_interview: atualizar score"]
    triage -->|"cambio"| exchange["exchange: cotacao via Tavily"]
    credit -->|"rejeitado e aceita entrevista"| interview
    credit --> endNode["end"]
    interview --> credit
    exchange --> endNode
```

O DeepSeek via OpenRouter classifica intencoes depois da autenticacao. O modelo retorna JSON com `intent` e `confidence`, validado localmente com Pydantic. Se nao houver LLM configurado ou ocorrer falha tecnica, existe fallback deterministico por palavras-chave.

As regras bancarias ficam fora do LLM: autenticacao, score, aprovacao de limite e escrita em CSV sao executadas por Python para manter auditabilidade.

## Funcionalidades

- Autenticacao por CPF e data de nascimento via `data/clientes.csv`.
- Limite de tres tentativas de autenticacao.
- Triagem agentic de intencao com DeepSeek/OpenRouter.
- Consulta de limite de credito.
- Solicitacao de aumento de limite com registro em CSV.
- Aprovacao ou rejeicao por score usando `data/score_limite.csv`.
- Entrevista financeira para recalcular score.
- Atualizacao do score em `data/clientes.csv`.
- Consulta de cambio em tempo real via Tavily.
- UI simples em Streamlit.
- Observabilidade com LangSmith.
- Eval offline de classificacao de intencao com LangSmith.
- Testes automatizados para regras e fluxo principal.

## Observabilidade e Evals

O projeto usa LangSmith de forma enxuta, focado no que mais importa para um sistema agentic:

- `src/observability.py` registra um resumo sanitizado de cada turno.
- CPFs sao mascarados antes de aparecerem em metadados de trace.
- `evals/datasets/intent_cases.jsonl` contem casos pequenos de classificacao de intencao.
- `evals/run_intent_eval.py` cria/reusa o dataset no LangSmith e executa a metrica `intent_accuracy`.

Ultima execucao real da eval:

- Experimento: `intent-classifier-18da535d`
- Casos: `6`
- `intent_accuracy`: `1.0`
- `error_rate`: `0.0`
- Tokens totais: `1608`

## Estrutura do Projeto

```text
.
├── app.py
├── data/
│   ├── clientes.csv
│   ├── score_limite.csv
│   └── solicitacoes_aumento_limite.csv
├── docs/
│   └── challenge/
│       └── desafio-tecnico-agentes-ia-bianca.pdf
├── evals/
│   ├── datasets/
│   │   └── intent_cases.jsonl
│   └── run_intent_eval.py
├── src/
│   ├── graph.py
│   ├── llm.py
│   ├── observability.py
│   ├── schemas.py
│   ├── state.py
│   └── tools/
│       ├── auth.py
│       ├── credit.py
│       ├── exchange.py
│       └── scoring.py
├── tests/
└── .specs/
```

## Como Executar

Crie um arquivo `.env` baseado em `.env.example`:

```bash
OPENROUTER_API_KEY=sua_key_openrouter
OPENROUTER_MODEL=deepseek/deepseek-chat
TAVILY_API_KEY=sua_key_tavily
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=sua_key_langsmith
LANGSMITH_PROJECT=desafio-agentes-ia-banco-agil
```

Instale as dependencias:

```bash
python -m pip install -e ".[dev]"
```

Rode a interface:

```bash
streamlit run app.py
```

Rode a eval de intencao:

```bash
python -m evals.run_intent_eval
```

Dados de teste para autenticacao:

```text
CPF: 12345678900
Data de nascimento: 1990-05-10
```

Exemplos de mensagens:

```text
Meu CPF e 12345678900 e nasci em 1990-05-10
Quero consultar meu limite
Quero aumento para 8000
Quero fazer entrevista de credito. renda 6000 emprego formal despesas 2000 dependentes 1 dividas nao
Qual a cotacao do dolar hoje?
```

## Testes

```bash
python -m pytest
```

A suite cobre autenticacao, credito, score, cambio via cliente Tavily fake, roteamento do grafo, privacidade da triagem, sanitizacao de CPF e evaluator de intencao.

## Decisoes Tecnicas

- **LangGraph**: orquestra o atendimento como grafo de estados.
- **OpenRouter + DeepSeek**: classifica intencoes com JSON estruturado validado por Pydantic.
- **Tavily**: consulta cotacoes de moedas.
- **LangSmith**: fornece tracing e eval offline sem adicionar MLOps pesado.
- **CSV**: atende ao desafio com persistencia simples e auditavel.
- **SDD**: documenta requisitos, design e tarefas em `.specs/`.

## Desafios Resolvidos

O desafio pedia agentes especializados, mas tambem uma conversa unica para o cliente. A solucao modela os agentes como capacidades internas de um unico grafo, preservando escopo e fluidez.

Outro cuidado foi manter decisoes bancarias deterministicas. O LLM entende a conversa, mas nao aprova credito nem calcula score.
