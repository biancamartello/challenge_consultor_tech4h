# Design: Banking Assistant

## Decisao Arquitetural

A solucao usa um unico `BankingAssistantGraph` em LangGraph. Os agentes do enunciado sao modelados como capacidades internas do grafo, preservando uma experiencia continua para o cliente.

## Componentes

- `app.py`: UI em Streamlit.
- `src/graph.py`: montagem do `StateGraph`, nos e rotas.
- `src/state.py`: estado compartilhado do atendimento.
- `src/llm.py`: configuracao do DeepSeek via OpenRouter.
- `src/observability.py`: tracing sanitizado para LangSmith.
- `src/tools/auth.py`: autenticacao via CSV.
- `src/tools/credit.py`: limite, solicitacao e decisao de aumento.
- `src/tools/scoring.py`: calculo e atualizacao de score.
- `src/tools/exchange.py`: consulta de cambio via Tavily.
- `src/schemas.py`: modelos estruturados para intencao e entrevista.
- `evals/run_intent_eval.py`: runner de avaliacao offline de intencao no LangSmith.
- `evals/datasets/intent_cases.jsonl`: dataset pequeno de casos de intencao.

## Fluxo

```mermaid
flowchart TD
    user["Cliente"] --> ui["Streamlit"]
    ui --> graph["BankingAssistantGraph"]
    graph --> triage["triage"]
    triage -->|"credito"| credit["credit"]
    triage -->|"entrevista"| interview["credit_interview"]
    triage -->|"cambio"| exchange["exchange"]
    credit -->|"rejeitado e aceita entrevista"| interview
    interview --> credit
    credit --> endNode["end"]
    exchange --> endNode
```

## Regras

- O LLM e o caminho principal para classificacao de intencao depois da autenticacao.
- A classificacao de intencao pede JSON valido ao LLM e valida a resposta localmente com `IntentResult`, contendo `intent` e `confidence`.
- O fallback por palavras-chave existe apenas para execucao local sem `OPENROUTER_API_KEY` ou falha tecnica do provedor.
- Se o LLM retornar `unknown`, essa decisao e preservada; o grafo deve pedir esclarecimento em vez de forcar uma rota por heuristica.
- LLM tambem pode apoiar respostas conversacionais, mas nao decide regras bancarias.
- Python executa regras auditaveis: autenticacao, score, limite, CSV e API externa.
- Tavily fica encapsulado em `src/tools/exchange.py`, permitindo teste com cliente falso.
- OpenRouter fica encapsulado em `src/llm.py`, permitindo troca de modelo via `.env`.
- LangSmith registra observabilidade leve de turnos do atendimento com metadados sanitizados.
- Evals no LangSmith focam na triagem agentic; regras deterministicas continuam validadas por `pytest`.

## Triagem Agentic

O no `triage` chama `classify_intent()`. Essa funcao tenta primeiro obter um modelo em runtime via `src/llm.py`. Quando disponivel, o modelo recebe um prompt de dominio do Banco Agil e retorna um JSON estruturado com uma das intencoes validas:

- `credit`
- `credit_interview`
- `exchange`
- `end`
- `unknown`

Esse desenho evita depender apenas de palavras-chave. Por exemplo, uma frase como "queria melhorar meu poder de compra no cartao" deve ser interpretada pelo LLM como `credit`, mesmo sem conter literalmente "limite" ou "credito".

O parsing do JSON e feito pela aplicacao com Pydantic. Essa escolha preserva saida estruturada e evita warnings de serializacao no LangSmith causados por objetos Pydantic acoplados diretamente ao retorno bruto do provedor.

## Observabilidade e Evals

O tracing usa `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, `LANGSMITH_ENDPOINT` e `LANGSMITH_PROJECT`. A UI registra um resumo sanitizado de cada turno, incluindo rota, intencao e estado de autenticacao, sem expor CPF completo.

A avaliacao offline usa um dataset pequeno de classificacao de intencao. O target chama `classify_intent()` e o evaluator `intent_accuracy` compara a intencao prevista com a esperada. Isso demonstra dominio de evals sem aumentar a complexidade do desafio.
