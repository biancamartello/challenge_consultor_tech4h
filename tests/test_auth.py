import csv

from src.tools.auth import authenticate_client


def write_clients(path):
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


def test_authenticates_client_with_matching_cpf_and_birth_date(tmp_path):
    clients_path = tmp_path / "clientes.csv"
    write_clients(clients_path)

    result = authenticate_client("123.456.789-00", "1990-05-10", clients_path)

    assert result.authenticated is True
    assert result.client is not None
    assert result.client["nome"] == "Bianca"


def test_authenticates_client_with_brazilian_birth_date_format(tmp_path):
    clients_path = tmp_path / "clientes.csv"
    write_clients(clients_path)

    result = authenticate_client("12345678900", "10/05/1990", clients_path)

    assert result.authenticated is True
    assert result.client is not None


def test_authenticates_client_with_brazilian_dash_birth_date_format(tmp_path):
    clients_path = tmp_path / "clientes.csv"
    write_clients(clients_path)

    result = authenticate_client("12345678900", "10-05-1990", clients_path)

    assert result.authenticated is True
    assert result.client is not None


def test_rejects_client_when_birth_date_does_not_match(tmp_path):
    clients_path = tmp_path / "clientes.csv"
    write_clients(clients_path)

    result = authenticate_client("12345678900", "1991-05-10", clients_path)

    assert result.authenticated is False
    assert result.client is None
