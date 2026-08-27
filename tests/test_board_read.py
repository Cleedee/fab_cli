"""Testes para board e read (navegação de cartas na mesa)."""

import pytest

from flesh_and_blood.app import (
    _BrowseCard,
    _BrowseIndex,
    _collect_board_cards,
)
from flesh_and_blood.carddb import load_cards
from flesh_and_blood.models import Hero, new_game


@pytest.fixture()
def cards():
    return load_cards()


@pytest.fixture()
def empty_game():
    hero_a = Hero("Briar, Warden of Thorns", "Briar", 20, 4, ("Runeblade",), ())
    hero_b = Hero("Enigma", "Enigma", 20, 4, ("Illusionist",), ())
    return new_game(hero_a, hero_b)


@pytest.fixture()
def game_with_cards(empty_game):
    """Jogo com cartas nas mãos, arma, arsenal e auras."""
    gs = empty_game

    # Mão A: 3 cartas
    gs.players["A"].hand = ["Snatch (red)", "Entangle (blue)", "Sigil of Solace (red)"]
    gs.players["A"].weapons = ["Star Fall"]
    gs.players["A"].arsenal = "Nebula CD (yellow)"

    # Mão B: 2 cartas
    gs.players["B"].hand = ["Phantasmal Footsteps", "Sink Below (red)"]
    gs.players["B"].equipment_uses = {"Nullrune Boots": None}
    gs.players["B"].add_aura("Spectral Shield", 2)

    return gs


# ── _BrowseIndex ───────────────────────────────────────────────────


def test_browse_index_get():
    cards_list = [
        _BrowseCard(1, "A", "A", "hand", "Mão A"),
        _BrowseCard(2, "B", "A", "hand", "Mão A"),
    ]
    idx = _BrowseIndex(cards_list)
    assert idx.get().idx == 1
    assert idx.total == 2


def test_browse_index_next():
    cards_list = [
        _BrowseCard(1, "A", "A", "hand", "Mão A"),
        _BrowseCard(2, "B", "A", "hand", "Mão A"),
        _BrowseCard(3, "C", "B", "hand", "Mão B"),
    ]
    idx = _BrowseIndex(cards_list)
    assert idx.get().idx == 1
    bc = idx.next()
    assert bc is not None and bc.idx == 2
    bc = idx.next()
    assert bc is not None and bc.idx == 3
    # No fim da lista
    bc = idx.next()
    assert bc is not None and bc.idx == 3  # permanece


def test_browse_index_prev():
    cards_list = [
        _BrowseCard(1, "A", "A", "hand", "Mão A"),
        _BrowseCard(2, "B", "A", "hand", "Mão A"),
    ]
    idx = _BrowseIndex(cards_list, current=1)
    assert idx.get().idx == 2
    bc = idx.prev()
    assert bc is not None and bc.idx == 1
    # No início
    bc = idx.prev()
    assert bc is not None and bc.idx == 1  # permanece


def test_browse_index_empty():
    idx = _BrowseIndex([])
    assert idx.get() is None
    assert idx.next() is None
    assert idx.prev() is None
    assert idx.total == 0


# ── _collect_board_cards ───────────────────────────────────────────


def test_collect_empty_board(cards, empty_game):
    result = _collect_board_cards(empty_game, cards)
    assert result == []


def test_collect_hands(cards, game_with_cards):
    result = _collect_board_cards(game_with_cards, cards)
    hand_a = [c for c in result if c.location == "hand" and c.side == "A"]
    hand_b = [c for c in result if c.location == "hand" and c.side == "B"]
    assert len(hand_a) == 3
    assert len(hand_b) == 2


def test_collect_weapons(cards, game_with_cards):
    result = _collect_board_cards(game_with_cards, cards)
    weapons = [c for c in result if c.location == "weapon"]
    assert len(weapons) == 1
    assert weapons[0].key == "Star Fall"


def test_collect_equipment(cards, game_with_cards):
    result = _collect_board_cards(game_with_cards, cards)
    equip = [c for c in result if c.location == "equipment"]
    assert len(equip) == 1
    assert equip[0].key == "Nullrune Boots"


def test_collect_arsenal(cards, game_with_cards):
    result = _collect_board_cards(game_with_cards, cards)
    arsenal = [c for c in result if c.location == "arsenal"]
    assert len(arsenal) == 1
    assert arsenal[0].key == "Nebula CD (yellow)"


def test_collect_auras(cards, game_with_cards):
    result = _collect_board_cards(game_with_cards, cards)
    auras = [c for c in result if c.location == "aura"]
    assert len(auras) == 1
    assert auras[0].key == "Spectral Shield"


def test_collect_indices_sequential(cards, game_with_cards):
    result = _collect_board_cards(game_with_cards, cards)
    indices = [c.idx for c in result]
    assert indices == list(range(1, len(result) + 1))


def test_collect_destroyed_equipment_not_shown(cards, game_with_cards):
    game_with_cards.players["B"].equipment_destroyed.append("Nullrune Boots")
    result = _collect_board_cards(game_with_cards, cards)
    equip = [c for c in result if c.location == "equipment"]
    assert len(equip) == 0
