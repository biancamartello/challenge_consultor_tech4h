from src.observability import build_turn_metadata, mask_cpf, sanitize_text


def test_masks_cpf_without_exposing_full_identifier():
    assert mask_cpf("123.456.789-00") == "***8900"


def test_sanitizes_cpf_inside_free_text():
    text = sanitize_text("Meu CPF e 12345678900 e quero consultar limite")

    assert "12345678900" not in text
    assert "***8900" in text


def test_builds_trace_metadata_without_raw_cpf():
    metadata = build_turn_metadata(
        {"cpf": "12345678900", "authenticated": True, "intent": "credit"},
        route="credit",
    )

    assert metadata["cpf_masked"] == "***8900"
    assert "cpf" not in metadata
    assert metadata["authenticated"] is True
    assert metadata["intent"] == "credit"
    assert metadata["route"] == "credit"
