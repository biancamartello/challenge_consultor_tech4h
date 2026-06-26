from __future__ import annotations

import streamlit as st
from dotenv import load_dotenv

from src.graph import build_graph
from src.observability import build_turn_metadata, record_turn_trace, sanitize_text


load_dotenv()


@st.cache_resource
def get_graph():
    return build_graph()


def initialize_session() -> None:
    if "agent_state" not in st.session_state:
        st.session_state.agent_state = {
            "authenticated": False,
            "auth_attempts": 0,
            "should_end": False,
        }
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": "Ola, eu sou o assistente do Banco Agil. Informe CPF e data de nascimento para comecar.",
            }
        ]


def main() -> None:
    st.set_page_config(page_title="Banco Agil Agent", page_icon="BA")
    st.title("Banco Agil - Atendimento Inteligente")
    st.caption("LangGraph + OpenRouter/DeepSeek + Tavily")

    initialize_session()
    graph = get_graph()

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    prompt = st.chat_input("Digite sua mensagem")
    if not prompt:
        return

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    try:
        next_state = graph.invoke({**st.session_state.agent_state, "user_input": prompt})
        st.session_state.agent_state.update(next_state)
        response = st.session_state.agent_state.get("response", "Nao consegui processar sua solicitacao.")
        metadata = build_turn_metadata(
            st.session_state.agent_state,
            route=st.session_state.agent_state.get("intent", "unknown"),
        )
        record_turn_trace(
            user_input_masked=sanitize_text(prompt),
            response_masked=sanitize_text(response),
            metadata=metadata,
        )
    except Exception as exc:  # UI boundary: keep failures friendly for the evaluator.
        response = f"Encontrei um problema ao processar sua solicitacao: {exc}"

    st.session_state.messages.append({"role": "assistant", "content": response})
    with st.chat_message("assistant"):
        st.write(response)


if __name__ == "__main__":
    main()
