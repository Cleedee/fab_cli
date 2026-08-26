"""Testes do módulo fabrary.py (cliente Fabrary compartilhado)."""

from fresh_and_blood.fabrary import card_key, extract_card_data, pitch_to_color


def test_pitch_to_color():
    assert pitch_to_color(1) == "red"
    assert pitch_to_color(2) == "yellow"
    assert pitch_to_color(3) == "blue"
    assert pitch_to_color(None) is None
    assert pitch_to_color(0) is None


def test_card_key_with_pitch():
    assert card_key("Snatch", 1) == "Snatch (red)"
    assert card_key("Snatch", 2) == "Snatch (yellow)"
    assert card_key("Snatch", 3) == "Snatch (blue)"


def test_card_key_without_pitch():
    assert card_key("Cosmo, Scroll of Ancestral Tapestry", None) == (
        "Cosmo, Scroll of Ancestral Tapestry"
    )
    assert card_key("Ironrot Legs", None) == "Ironrot Legs"


def test_extract_card_data_full():
    """A API GraphQL só expõe name, pitch e types."""
    fab_card = {
        "name": "Snatch",
        "pitch": "1",
        "types": ["Action"],
    }
    result = extract_card_data(fab_card, 1)
    assert result["name"] == "Snatch"
    assert result["color"] == "red"
    assert result["pitch"] == 1
    assert result["types"] == ["Action"]
    # Campos indisponíveis na API recebem defaults
    assert result["cost"] is None
    assert result["power"] is None
    assert result["defense"] is None
    assert result["keywords"] == []
    assert result["sa_legal"] is True


def test_extract_card_data_missing_fields():
    fab_card = {"name": "Test Card"}
    result = extract_card_data(fab_card, None)
    assert result["name"] == "Test Card"
    assert result["color"] is None
    assert result["pitch"] is None
    assert result["cost"] is None
    assert result["power"] is None
    assert result["defense"] is None
    assert result["types"] == []
    assert result["keywords"] == []
    assert result["text"] == ""
    assert result["sa_legal"] is True  # API não expõe banned; assume legal


def test_extract_card_data_banned():
    """A API GraphQL não expõe silverAgeBanned; sa_legal é sempre True."""
    fab_card = {"name": "Banned Card"}
    result = extract_card_data(fab_card, 1)
    assert result["sa_legal"] is True
