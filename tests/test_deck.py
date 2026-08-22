from pathlib import Path

import pytest

from fresh_and_blood.carddb import load_cards
from fresh_and_blood.deck import Decklist, load_decklist, validate

DECKS_DIR = Path(__file__).resolve().parents[1] / "data" / "decks"


@pytest.fixture(scope="module")
def cards():
    return load_cards()


@pytest.mark.parametrize("filename", ["briar_sa.yaml", "enigma_sa.yaml"])
def test_official_decks_are_valid(cards, filename: str) -> None:
    deck = load_decklist(DECKS_DIR / filename)
    errors = validate(deck, cards)
    assert errors == []


def test_pool_size_is_55(cards) -> None:
    for filename in ("briar_sa.yaml", "enigma_sa.yaml"):
        deck = load_decklist(DECKS_DIR / filename)
        assert deck.pool_size == 55


def test_too_many_copies_is_rejected(cards) -> None:
    deck = load_decklist(DECKS_DIR / "enigma_sa.yaml")
    some_key = next(iter(deck.deck_pool))
    deck.deck_pool[some_key] = 3
    assert any(some_key in e and "cópias" in e for e in validate(deck, cards))


def test_unknown_card_is_rejected(cards) -> None:
    deck = load_decklist(DECKS_DIR / "briar_sa.yaml")
    key = next(iter(deck.deck_pool))
    qty = deck.deck_pool.pop(key)
    deck.deck_pool["Carta Inexistente (red)"] = qty
    assert any("não encontrada" in e for e in validate(deck, cards))


def test_sa_illegal_card_is_rejected(cards) -> None:
    from fresh_and_blood.models import Card

    illegal = Card(
        key="Rosetta Thorn",
        name="Rosetta Thorn",
        color=None,
        pitch=None,
        cost=None,
        power=2,
        defense=None,
        types=("Elemental", "Lightning", "Runeblade", "Weapon", "Dagger"),
        keywords=("Go again",),
        text="",
        rarity="R",
        sa_legal=False,
    )
    registry = {**cards, illegal.key: illegal}
    deck = load_decklist(DECKS_DIR / "briar_sa.yaml")
    key = next(iter(deck.deck_pool))
    deck.deck_pool["Rosetta Thorn"] = deck.deck_pool[key]
    assert any("ilegal em Silver Age" in e for e in validate(deck, registry))


def test_wrong_class_for_hero_is_rejected(cards) -> None:
    deck = load_decklist(DECKS_DIR / "briar_sa.yaml")
    # carta Illusionist não pode entrar no pool da Briar
    key = next(iter(deck.deck_pool))
    deck.deck_pool["Waxing Specter (red)"] = deck.deck_pool[key]
    assert any("fora do card-pool do herói" in e for e in validate(deck, cards))


def test_decklist_dataclass_helpers() -> None:
    deck = Decklist(hero="X", source="", arena=["A"], deck_pool={"B (red)": 2})
    assert deck.pool_size == 3
    assert deck.all_keys() == {"A", "B (red)"}
