import src.graph as graph_module
from src.graph import classify_intent, route_after_triage, triage_node


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
