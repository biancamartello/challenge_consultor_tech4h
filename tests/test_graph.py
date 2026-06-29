import csv

import src.graph as graph_module
from src.graph import (
    classify_intent,
    credit_interview_node,
    credit_node,
    extract_requested_limit,
    route_after_credit,
    route_after_triage,
    triage_node,
)


class FakeTextLLM:
    def invoke(self, _messages):
        return type("Response", (), {"content": "exchange"})()


class FakeJsonLLM:
    def __init__(self, intent):
        self.intent = intent
        self.messages = None

    def invoke(self, messages):
        self.messages = messages
        content = f'{{"intent": "{self.intent}", "confidence": 0.92}}'
        return type("Response", (), {"content": content})()


class FakeAmountLLM:
    def __init__(self, amount):
        self.amount = amount

    def invoke(self, _messages):
        content = f'{{"requested_limit": {self.amount}}}'
        return type("Response", (), {"content": content})()


def _write_clients(path, *, cpf="12345678900", score="650", limite="2500.00"):
    with path.open("w", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["cpf", "nome", "data_nascimento", "limite_credito", "score"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "cpf": cpf,
                "nome": "Bianca",
                "data_nascimento": "1990-05-10",
                "limite_credito": limite,
                "score": score,
            }
        )


def _write_score_table(path):
    with path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["score_min", "score_max", "limite_maximo"])
        writer.writeheader()
        writer.writerow({"score_min": "0", "score_max": "499", "limite_maximo": "1000"})
        writer.writerow({"score_min": "500", "score_max": "699", "limite_maximo": "5000"})
        writer.writerow({"score_min": "700", "score_max": "1000", "limite_maximo": "10000"})


def test_classifies_credit_intent_from_limit_message():
    assert classify_intent("quero consultar meu limite") == "credit"


def test_classifies_exchange_intent_from_currency_message():
    assert classify_intent("qual a cotacao do dolar hoje?") == "exchange"


def test_classifies_intent_with_injected_llm():
    assert classify_intent("preciso saber o euro", llm=FakeTextLLM()) == "exchange"


def test_uses_json_llm_as_primary_intent_classifier():
    llm = FakeJsonLLM("credit")

    intent = classify_intent("queria melhorar meu poder de compra no cartao", llm=llm)

    assert intent == "credit"
    assert "JSON" in llm.messages[0][1]


def test_does_not_override_llm_unknown_with_keyword_fallback():
    llm = FakeJsonLLM("unknown")

    intent = classify_intent("quero consultar meu limite", llm=llm)

    assert intent == "unknown"


def test_routes_unauthenticated_state_to_end():
    route = route_after_triage({"authenticated": False, "should_end": False})

    assert route == "end"


def test_routes_authenticated_credit_state_to_credit_node():
    route = route_after_triage(
        {
            "authenticated": True,
            "should_end": False,
            "intent": "credit",
        }
    )

    assert route == "credit"


def test_triage_does_not_classify_intent_before_authentication(monkeypatch):
    def fail_if_called(_text):
        raise AssertionError("intent classification should happen only after authentication")

    monkeypatch.setattr(graph_module, "classify_intent", fail_if_called)

    response = triage_node(
        {
            "authenticated": False,
            "user_input": "Meu CPF e 12345678900 e nasci em 1990-05-10",
        }
    )

    assert "authenticated" in response


def test_triage_classifies_intent_after_authentication(monkeypatch):
    monkeypatch.setattr(graph_module, "classify_intent", lambda _text: "exchange")

    response = triage_node(
        {
            "authenticated": True,
            "user_input": "quanto esta o euro hoje?",
        }
    )

    assert response["intent"] == "exchange"


def test_triage_authenticates_with_brazilian_dash_birth_date(tmp_path, monkeypatch):
    clients_path = tmp_path / "clientes.csv"
    with clients_path.open("w", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["cpf", "nome", "data_nascimento", "limite_credito", "score"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "cpf": "12345678900",
                "nome": "Bianca",
                "data_nascimento": "1990-05-10",
                "limite_credito": "2500.00",
                "score": "650",
            }
        )
    monkeypatch.setattr(graph_module, "CLIENTS_PATH", clients_path)

    response = triage_node(
        {
            "authenticated": False,
            "user_input": "meu cpf e 12345678900 e nasci em 10-05-1990",
        }
    )

    assert response["authenticated"] is True
    assert response["client"]["nome"] == "Bianca"


def test_rejected_credit_increase_offers_interview_consent(tmp_path, monkeypatch):
    clients_path = tmp_path / "clientes.csv"
    score_path = tmp_path / "score_limite.csv"
    requests_path = tmp_path / "solicitacoes.csv"
    _write_clients(clients_path, score="650", limite="2500.00")
    _write_score_table(score_path)

    monkeypatch.setattr(graph_module, "CLIENTS_PATH", clients_path)
    monkeypatch.setattr(graph_module, "SCORE_LIMIT_PATH", score_path)
    monkeypatch.setattr(graph_module, "REQUESTS_PATH", requests_path)

    state = credit_node(
        {
            "authenticated": True,
            "cpf": "12345678900",
            "user_input": "quero aumentar meu limite para 8 mil",
            "intent": "credit",
        }
    )

    assert state["credit_status"] == "rejeitado"
    assert state["requested_limit"] == 8000
    assert state["active_flow"] == "credit_interview_offer"
    # consentimento ainda nao foi dado: nao deve ir direto para a entrevista
    assert route_after_credit(state) == "end"


def test_interview_consent_yes_routes_to_interview(tmp_path, monkeypatch):
    clients_path = tmp_path / "clientes.csv"
    _write_clients(clients_path)
    monkeypatch.setattr(graph_module, "CLIENTS_PATH", clients_path)

    state = credit_node(
        {
            "authenticated": True,
            "cpf": "12345678900",
            "active_flow": "credit_interview_offer",
            "user_input": "sim, quero fazer",
        }
    )

    assert state["active_flow"] == "credit_interview"
    assert route_after_credit(state) == "credit_interview"


def test_interview_consent_no_closes_gracefully(tmp_path, monkeypatch):
    clients_path = tmp_path / "clientes.csv"
    _write_clients(clients_path)
    monkeypatch.setattr(graph_module, "CLIENTS_PATH", clients_path)

    state = credit_node(
        {
            "authenticated": True,
            "cpf": "12345678900",
            "active_flow": "credit_interview_offer",
            "user_input": "agora nao, obrigada",
        }
    )

    assert state["active_flow"] == ""
    assert route_after_credit(state) == "end"
    assert "response" in state


def test_consult_limit_keeps_credit_flow_for_follow_up(tmp_path, monkeypatch):
    clients_path = tmp_path / "clientes.csv"
    _write_clients(clients_path)
    monkeypatch.setattr(graph_module, "CLIENTS_PATH", clients_path)

    state = credit_node(
        {
            "authenticated": True,
            "cpf": "12345678900",
            "user_input": "qual e meu limite?",
            "intent": "credit",
        }
    )

    assert state["active_flow"] == "credit_increase"


def test_active_flow_routes_unknown_follow_up_to_credit():
    route = route_after_triage(
        {
            "authenticated": True,
            "intent": "unknown",
            "active_flow": "credit_increase",
        }
    )

    assert route == "credit"


def test_credit_flow_processes_k_amount_and_offers_interview(tmp_path, monkeypatch):
    clients_path = tmp_path / "clientes.csv"
    score_path = tmp_path / "score_limite.csv"
    requests_path = tmp_path / "solicitacoes.csv"
    _write_clients(clients_path, cpf="98765432100", score="420", limite="1000.00")
    _write_score_table(score_path)

    monkeypatch.setattr(graph_module, "CLIENTS_PATH", clients_path)
    monkeypatch.setattr(graph_module, "SCORE_LIMIT_PATH", score_path)
    monkeypatch.setattr(graph_module, "REQUESTS_PATH", requests_path)

    state = credit_node(
        {
            "authenticated": True,
            "cpf": "98765432100",
            "user_input": "eu gostaria de ter uns 5k",
            "intent": "unknown",
            "active_flow": "credit_increase",
        }
    )

    assert state["requested_limit"] == 5000
    assert state["credit_status"] == "rejeitado"
    assert state["active_flow"] == "credit_interview_offer"


def test_extract_requested_limit_uses_llm_for_written_amount():
    assert extract_requested_limit("quero uns cinco mil", llm=FakeAmountLLM(5000)) == 5000


def test_extract_requested_limit_falls_back_without_llm():
    assert extract_requested_limit("quero 5k") == 5000


def test_interview_starts_by_asking_first_field(tmp_path, monkeypatch):
    clients_path = tmp_path / "clientes.csv"
    _write_clients(clients_path)
    monkeypatch.setattr(graph_module, "CLIENTS_PATH", clients_path)

    state = credit_interview_node(
        {
            "cpf": "12345678900",
            "active_flow": "credit_interview",
            "interview_answers": {},
            "interview_pending_field": "",
            "user_input": "sim",
        }
    )

    assert state["interview_pending_field"] == "renda_mensal"


def test_interview_collects_field_and_advances(tmp_path, monkeypatch):
    clients_path = tmp_path / "clientes.csv"
    _write_clients(clients_path)
    monkeypatch.setattr(graph_module, "CLIENTS_PATH", clients_path)

    state = credit_interview_node(
        {
            "cpf": "12345678900",
            "active_flow": "credit_interview",
            "interview_answers": {},
            "interview_pending_field": "renda_mensal",
            "user_input": "minha renda e 5000",
        }
    )

    assert state["interview_answers"]["renda_mensal"] == 5000
    assert state["interview_pending_field"] == "tipo_emprego"


def test_interview_completion_updates_score(tmp_path, monkeypatch):
    clients_path = tmp_path / "clientes.csv"
    _write_clients(clients_path, score="420", limite="1000.00")
    monkeypatch.setattr(graph_module, "CLIENTS_PATH", clients_path)

    answers = {
        "renda_mensal": 5000.0,
        "tipo_emprego": "formal",
        "despesas": 2000.0,
        "dependentes": 1,
    }
    state = credit_interview_node(
        {
            "cpf": "12345678900",
            "active_flow": "credit_interview",
            "interview_answers": answers,
            "interview_pending_field": "tem_dividas",
            "user_input": "nao tenho dividas",
        }
    )

    assert state["intent"] == "credit"
    assert state["active_flow"] == ""
    with clients_path.open() as file:
        rows = list(csv.DictReader(file))
    assert rows[0]["score"] != "420"
