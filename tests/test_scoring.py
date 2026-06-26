import csv

from src.tools.scoring import calculate_credit_score, update_client_score


def test_calculates_score_with_weighted_financial_answers():
    score = calculate_credit_score(
        renda_mensal=6000,
        tipo_emprego="formal",
        despesas=2000,
        dependentes=1,
        tem_dividas=False,
    )

    assert score == 570


def test_caps_score_at_one_thousand():
    score = calculate_credit_score(
        renda_mensal=50000,
        tipo_emprego="formal",
        despesas=1000,
        dependentes=0,
        tem_dividas=False,
    )

    assert score == 1000


def test_updates_client_score_in_csv(tmp_path):
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

    update_client_score("123.456.789-00", 720, clients_path)

    with clients_path.open(newline="") as file:
        rows = list(csv.DictReader(file))
    assert rows[0]["score"] == "720"
