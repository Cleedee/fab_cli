"""Testes do script build_cards.py."""

from scripts.build_cards import build_all_cards, to_entry


def test_to_entry_basic():
    card = {
        "name": "Snatch",
        "color": "Red",
        "pitch": "1",
        "cost": "0",
        "power": "3",
        "defense": "3",
        "types": ["Action"],
        "card_keywords": ["Go again"],
        "functional_text_plain": "When this hits, gain 1 action point.",
        "printings": [{"rarity": "C"}, {"rarity": "R"}],
        "silver_age_legal": True,
        "silver_age_banned": False,
    }
    entry = to_entry(card)
    assert entry["name"] == "Snatch"
    assert entry["color"] == "red"
    assert entry["pitch"] == 1
    assert entry["cost"] == 0
    assert entry["power"] == 3
    assert entry["defense"] == 3
    assert entry["types"] == ["Action"]
    assert entry["keywords"] == ["Go again"]
    assert entry["rarity"] == "C"
    assert entry["sa_legal"] is True


def test_to_entry_empty_types_becomes_token():
    card = {
        "name": "Marked",
        "color": "",
        "pitch": "",
        "cost": "",
        "power": "",
        "defense": "",
        "types": [],
        "card_keywords": ["Mark"],
        "functional_text_plain": "You are marked.",
        "printings": [{"rarity": "T"}],
        "silver_age_legal": True,
        "silver_age_banned": False,
    }
    entry = to_entry(card)
    assert entry["types"] == ["Token"]


def test_to_entry_empty_numeric_fields():
    card = {
        "name": "Test",
        "color": "",
        "pitch": "",
        "cost": "abc",
        "power": "",
        "defense": "",
        "types": ["Action"],
        "card_keywords": [],
        "functional_text_plain": "",
        "printings": [],
        "silver_age_legal": False,
        "silver_age_banned": False,
    }
    entry = to_entry(card)
    assert entry["pitch"] is None
    assert entry["cost"] is None
    assert entry["power"] is None


def test_build_all_cards():
    cards = [
        {
            "name": "Snatch",
            "color": "Red",
            "pitch": "1",
            "cost": "0",
            "power": "3",
            "defense": "3",
            "types": ["Action"],
            "card_keywords": [],
            "functional_text_plain": "",
            "printings": [{"rarity": "C"}],
            "silver_age_legal": True,
            "silver_age_banned": False,
        },
        {
            "name": "Snatch",
            "color": "Yellow",
            "pitch": "2",
            "cost": "0",
            "power": "2",
            "defense": "3",
            "types": ["Action"],
            "card_keywords": [],
            "functional_text_plain": "",
            "printings": [{"rarity": "C"}],
            "silver_age_legal": True,
            "silver_age_banned": False,
        },
        {
            "name": "Ironrot Legs",
            "color": "",
            "pitch": "",
            "cost": "",
            "power": "",
            "defense": "1",
            "types": ["Equipment"],
            "card_keywords": [],
            "functional_text_plain": "",
            "printings": [{"rarity": "C"}],
            "silver_age_legal": True,
            "silver_age_banned": False,
        },
    ]
    out = build_all_cards(cards)
    assert "Snatch (red)" in out
    assert "Snatch (yellow)" in out
    assert "Ironrot Legs" in out
    assert out["Snatch (red)"]["pitch"] == 1
    assert out["Snatch (yellow)"]["pitch"] == 2
    assert out["Ironrot Legs"]["color"] is None


def test_build_all_cards_banned():
    cards = [
        {
            "name": "Banned Card",
            "color": "Red",
            "pitch": "1",
            "cost": "0",
            "power": "3",
            "defense": "3",
            "types": ["Action"],
            "card_keywords": [],
            "functional_text_plain": "",
            "printings": [{"rarity": "C"}],
            "silver_age_legal": True,
            "silver_age_banned": True,
        },
    ]
    out = build_all_cards(cards)
    assert out["Banned Card (red)"]["sa_legal"] is False
