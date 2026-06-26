import csv

from src.tools.credit import request_credit_increase


def write_clients(path, score="650"):
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
                "score": score,
            }
        )


def write_score_table(path):
    with path.open("w", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["score_min", "score_max", "limite_maximo"],
        )
        writer.writeheader()
        writer.writerow({"score_min": "0", "score_max": "499", "limite_maximo": "1000"})
        writer.writerow({"score_min": "500", "score_max": "699", "limite_maximo": "5000"})
        writer.writerow({"score_min": "700", "score_max": "1000", "limite_maximo": "10000"})


def read_requests(path):
    with path.open(newline="") as file:
        return list(csv.DictReader(file))


def test_approves_limit_request_when_score_allows_amount(tmp_path):
    clients_path = tmp_path / "clientes.csv"
    score_path = tmp_path / "score_limite.csv"
    requests_path = tmp_path / "solicitacoes.csv"
    write_clients(clients_path, score="650")
    write_score_table(score_path)

    decision = request_credit_increase(
        "12345678900",
        4000,
        clients_path,
        score_path,
        requests_path,
    )

    assert decision.status == "aprovado"
    assert decision.max_allowed_limit == 5000
    rows = read_requests(requests_path)
    assert rows[0]["cpf_cliente"] == "12345678900"
    assert rows[0]["status_pedido"] == "aprovado"


def test_rejects_limit_request_when_score_does_not_allow_amount(tmp_path):
    clients_path = tmp_path / "clientes.csv"
    score_path = tmp_path / "score_limite.csv"
    requests_path = tmp_path / "solicitacoes.csv"
    write_clients(clients_path, score="650")
    write_score_table(score_path)

    decision = request_credit_increase(
        "12345678900",
        8000,
        clients_path,
        score_path,
        requests_path,
    )

    assert decision.status == "rejeitado"
    assert decision.max_allowed_limit == 5000
    rows = read_requests(requests_path)
    assert rows[0]["status_pedido"] == "rejeitado"
