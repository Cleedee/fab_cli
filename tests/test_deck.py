from pathlib import Path

import pytest

from fresh_and_blood.carddb import load_cards
from fresh_and_blood.deck import (
    Decklist,
    allowed_types_for,
    hero_from_deck,
    load_decklist,
    validate,
    weapon_from_deck,
)

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


def test_hero_from_deck_derives_hero(cards) -> None:
    deck = load_decklist(DECKS_DIR / "briar_sa.yaml")
    hero = hero_from_deck(deck, cards)
    assert hero.name == "Briar, Warden of Thorns"
    assert hero.life == 20
    assert hero.intellect == 4
    assert "Runeblade" in hero.classes


def test_weapon_from_deck_returns_first_weapon(cards) -> None:
    deck = load_decklist(DECKS_DIR / "enigma_sa.yaml")
    assert weapon_from_deck(deck, cards) == "Cosmo, Scroll of Ancestral Tapestry"


def test_allowed_types_fallback_para_heroi_novo(cards) -> None:
    """Herói não mapeado usa os types do card do herói (menos Hero/Young)."""
    from fresh_and_blood.models import Card

    novo = Card(
        key="Nova",
        name="Nova",
        color=None,
        pitch=None,
        cost=None,
        power=None,
        defense=None,
        types=("Shadow", "Runeblade", "Hero", "Young"),
        keywords=(),
        text="",
        rarity="C",
        sa_legal=True,
    )
    registry = {**cards, novo.key: novo}
    tipos = allowed_types_for("Nova", registry)
    assert tipos is not None
    assert "Shadow" in tipos and "Runeblade" in tipos and "Generic" in tipos
    assert "Hero" not in tipos and "Young" not in tipos

    deck = Decklist(hero="Nova", source="", arena=[], deck_pool={})
    hero = hero_from_deck(deck, registry)
    assert hero.classes == ("Shadow", "Runeblade")


def test_weapon_from_deck_none_sem_arma(cards) -> None:
    deck = Decklist(hero="Enigma", source="", arena=["Blade Beckoner Helm"], deck_pool={})
    assert weapon_from_deck(deck, cards) is None
