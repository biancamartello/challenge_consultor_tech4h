"""Testes de integracao do grafo montado (build_graph + invoke).

Diferente de test_graph.py, que exercita cada no isoladamente, estes testes
validam a FIACAO real: arestas condicionais, roteamento e o fluxo START -> ... -> END.
"""

import csv

import src.graph as graph_module
from src.graph import build_graph


def _write_clients(path):
    with path.open("w", newline="") as file:
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


def test_graph_authenticates_and_routes_end_to_end(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    clients_path = tmp_path / "clientes.csv"
    _write_clients(clients_path)
    monkeypatch.setattr(graph_module, "CLIENTS_PATH", clients_path)

    graph = build_graph()
    state = graph.invoke(
        {
            "authenticated": False,
            "user_input": "meu cpf e 12345678900 e nasci em 10/05/1990",
        }
    )

    assert state["authenticated"] is True
    assert state["client"]["nome"] == "Bianca"
    assert state["response"]


def test_graph_ends_conversation_on_user_request(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    graph = build_graph()
    state = graph.invoke(
        {
            "authenticated": True,
            "client": {"nome": "Bianca", "cpf": "12345678900"},
            "user_input": "quero encerrar, obrigada",
        }
    )

    assert state["should_end"] is True
    assert "encerr" in state["response"].lower()
