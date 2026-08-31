"""Testes para board e read (navegação de cartas na mesa)."""

import pytest

from flesh_and_blood.app import (
    _BrowseCard,
    _collect_board_cards,
    _entry_summary,
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


# ── _entry_summary ────────────────────────────────────────────────


def test_entry_summary_com_card(cards):
    entry = _BrowseCard(3, "Snatch (red)", "A", "hand", "Mão A")
    summary = _entry_summary(entry, cards["Snatch (red)"])
    assert "[3]" in summary
    assert "Mão A" in summary
    assert "Snatch (red)" in summary


def test_entry_summary_sem_card(cards):
    entry = _BrowseCard(1, "Carta Desconhecida", "B", "aura", "Aura B")
    summary = _entry_summary(entry, None)
    assert "[1]" in summary
    assert "Carta Desconhecida" in summary


def test_entry_summary_equipamento(cards):
    entry = _BrowseCard(2, "Nullrune Boots", "B", "equipment", "Legs")
    summary = _entry_summary(entry, cards["Nullrune Boots"])
    assert "Legs" in summary
    assert "Nullrune Boots" in summary


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


# ── Cemitério e banidas ────────────────────────────────────────────


def test_collect_graveyard(cards, empty_game):
    empty_game.players["A"].graveyard = ["Gleeful Grin (red)", "Sink Below (blue)"]
    result = _collect_board_cards(empty_game, cards)
    grave = [c for c in result if c.location == "graveyard"]
    assert len(grave) == 2
    assert all(c.side == "A" for c in grave)
    assert {c.key for c in grave} == {"Gleeful Grin (red)", "Sink Below (blue)"}
    assert all("Cemitério A" in c.label for c in grave)


def test_collect_banished(cards, empty_game):
    empty_game.players["B"].banished = ["Channel Lake Frigid", "Nimble Strike (yellow)"]
    result = _collect_board_cards(empty_game, cards)
    banned = [c for c in result if c.location == "banished"]
    assert len(banned) == 2
    assert all(c.side == "B" for c in banned)
    assert all("Banidas B" in c.label for c in banned)


def test_collect_piles_indices_sequential(cards, empty_game):
    empty_game.players["A"].graveyard = ["Energy Potion (red)"]
    empty_game.players["B"].banished = ["Nullrune Boots"]
    result = _collect_board_cards(empty_game, cards)
    indices = [c.idx for c in result]
    assert indices == list(range(1, len(result) + 1))
