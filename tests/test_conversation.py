from src.conversation import (
    auth_success_response,
    build_short_history,
    current_limit_response,
    normalize_response_text,
    to_streamlit_safe,
)


class FakeHumanizeLLM:
    def __init__(self):
        self.messages = None

    def invoke(self, messages):
        self.messages = messages
        return type("Response", (), {"content": "Continuando sem repetir saudacao."})()


def test_normalizes_llm_response_to_plain_text():
    text = normalize_response_text("**Oi, Bia!**\n- Posso te ajudar com o limite?\n# Banco Agil")

    assert "**" not in text
    assert "\n" not in text
    assert "#" not in text
    assert text == "Oi, Bia! Posso te ajudar com o limite? Banco Agil"


def test_escapes_dollar_sign_for_streamlit():
    safe = to_streamlit_safe("Seu limite e R$ 1.000,00 e ate R$ 5.000,00")

    assert "$" not in safe.replace("\\$", "")
    assert safe == "Seu limite e R\\$ 1.000,00 e ate R\\$ 5.000,00"
    assert safe.replace("\\$", "$") == "Seu limite e R$ 1.000,00 e ate R$ 5.000,00"


def test_build_short_history_truncates_and_sanitizes():
    messages = [
        {"role": "assistant", "content": "Ola!"},
        {"role": "user", "content": "Meu CPF e 12345678900"},
        {"role": "assistant", "content": "Limite R\\$ 1.000,00"},
        {"role": "user", "content": "quero aumentar"},
        {"role": "assistant", "content": "Qual valor?"},
        {"role": "user", "content": "5k"},
        {"role": "assistant", "content": "Analisando"},
        {"role": "user", "content": "ok"},
    ]

    history = build_short_history(messages, max_messages=4)

    assert len(history) == 4
    assert history[0] == ("assistant", "Qual valor?")
    assert history[1] == ("user", "5k")
    assert history[2] == ("assistant", "Analisando")
    assert history[3] == ("user", "ok")

    full_history = build_short_history(messages)
    cpf_turn = next(content for role, content in full_history if role == "user" and "CPF" in content)
    assert "12345678900" not in cpf_turn
    assert "***" in cpf_turn


def test_humanize_passes_short_history_to_llm(monkeypatch):
    fake = FakeHumanizeLLM()
    monkeypatch.setattr("src.conversation.get_chat_model", lambda **kwargs: fake)

    history = [
        ("user", "Oi, tudo bem?"),
        ("assistant", "Me envie seu CPF."),
        ("user", "98765432100"),
    ]
    result = auth_success_response("Carlos", history=history)

    assert result == "Continuando sem repetir saudacao."
    assert fake.messages is not None
    assert fake.messages[0][0] == "system"
    assert fake.messages[1] == ("human", "Oi, tudo bem?")
    assert fake.messages[2] == ("ai", "Me envie seu CPF.")
    assert fake.messages[3] == ("human", "98765432100")
    assert fake.messages[4][0] == "human"
    assert "autenticacao foi bem-sucedida" in fake.messages[4][1]
    assert "nome = Carlos" in fake.messages[4][1]


def test_humanize_injects_official_client_name_guard(monkeypatch):
    fake = FakeHumanizeLLM()
    monkeypatch.setattr("src.conversation.get_chat_model", lambda **kwargs: fake)

    history = [
        ("assistant", "Perfeito, Carlos! Como posso ajudar?"),
        ("user", "qual e meu limite?"),
    ]
    current_limit_response(current_limit=500.0, history=history, client_name="Manasses")

    assert fake.messages is not None
    instruction = fake.messages[-1][1]
    assert "nome = Manasses" in instruction
    assert "EXCLUSIVAMENTE 'Manasses'" in instruction
