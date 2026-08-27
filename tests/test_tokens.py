"""Testes do sistema de tokens (criação, remoção, ativação e triggers)."""

import pytest

from flesh_and_blood.carddb import load_cards
from flesh_and_blood.combat import (
    CombatError,
    create_token,
    end_turn,
    remove_token,
    start_turn,
    use_item_token,
)
from flesh_and_blood.deck import hero_from_deck, load_decklist
from flesh_and_blood.models import GameState, new_game


@pytest.fixture(scope="module")
def cards():
    return load_cards()


@pytest.fixture(scope="module")
def decks():
    a = load_decklist("data/decks/briar_sa.yaml")
    b = load_decklist("data/decks/enigma_sa.yaml")
    return a, b


@pytest.fixture(scope="module")
def heroes(cards, decks):
    return hero_from_deck(decks[0], cards), hero_from_deck(decks[1], cards)


def _state(heroes) -> GameState:
    return new_game(heroes[0], heroes[1], "A")


# --- Model: add_token / pop_token ---


def test_add_token_pop_token(heroes):
    p = _state(heroes).players["A"]
    p.add_token("Gold", 2)
    assert p.tokens["Gold"] == 2
    remaining = p.pop_token("Gold", 1)
    assert remaining == 1
    assert p.tokens["Gold"] == 1
    remaining = p.pop_token("Gold", 1)
    assert remaining == 0
    assert "Gold" not in p.tokens


def test_pop_token_mais_do_que_tem(heroes):
    p = _state(heroes).players["A"]
    p.add_token("Gold", 2)
    remaining = p.pop_token("Gold", 5)
    assert remaining == 0
    assert "Gold" not in p.tokens


def test_pop_token_inexistente(heroes):
    p = _state(heroes).players["A"]
    remaining = p.pop_token("Gold", 1)
    assert remaining == 0


# --- create_token / remove_token ---


def test_create_item_token(heroes):
    state = _state(heroes)
    notice = create_token(state, "A", "Gold", 2)
    assert "Gold" in notice.text
    assert state.players["A"].tokens["Gold"] == 2


def test_create_aura_token(heroes):
    state = _state(heroes)
    notice = create_token(state, "A", "Spectral Shield")
    assert "Spectral Shield" in notice.text
    assert "Spectral Shield" in state.players["A"].auras
    assert len(state.players["A"].auras["Spectral Shield"]) == 1


def test_remove_item_token(heroes):
    state = _state(heroes)
    create_token(state, "A", "Gold", 3)
    notice = remove_token(state, "A", "Gold", 2)
    assert "Gold" in notice.text
    assert state.players["A"].tokens["Gold"] == 1


def test_remove_aura_token(heroes):
    state = _state(heroes)
    create_token(state, "A", "Spectral Shield")
    create_token(state, "A", "Spectral Shield")
    assert len(state.players["A"].auras["Spectral Shield"]) == 2
    notice = remove_token(state, "A", "Spectral Shield", 1)
    assert "Spectral Shield" in notice.text
    assert len(state.players["A"].auras["Spectral Shield"]) == 1


# --- use_item_token ---


def test_use_gold(heroes, cards):
    state = _state(heroes)
    state.players["A"].pitch_pool = 3
    create_token(state, "A", "Gold", 1)
    notice = use_item_token(state, "A", "Gold", cards)
    assert "Gold" in notice.text
    assert state.players["A"].pitch_pool == 1  # pagou 2
    assert state.players["A"].tokens.get("Gold", 0) == 0


def test_use_gold_sem_custo_levanta_erro(heroes, cards):
    state = _state(heroes)
    state.players["A"].pitch_pool = 0
    create_token(state, "A", "Gold", 1)
    with pytest.raises(CombatError, match="insuficiente"):
        use_item_token(state, "A", "Gold", cards)


def test_use_gold_sem_token_levanta_erro(heroes, cards):
    state = _state(heroes)
    state.players["A"].pitch_pool = 3
    with pytest.raises(CombatError, match="nenhum Gold"):
        use_item_token(state, "A", "Gold", cards)


def test_use_silver(heroes, cards):
    state = _state(heroes)
    state.players["A"].pitch_pool = 5
    create_token(state, "A", "Silver", 1)
    notice = use_item_token(state, "A", "Silver", cards)
    assert "Silver" in notice.text
    assert state.players["A"].pitch_pool == 2  # pagou 3


def test_use_copper(heroes, cards):
    state = _state(heroes)
    state.players["A"].pitch_pool = 6
    create_token(state, "A", "Copper", 1)
    notice = use_item_token(state, "A", "Copper", cards)
    assert "Copper" in notice.text
    assert state.players["A"].pitch_pool == 2  # pagou 4


def test_use_token_nao_item_levanta_erro(heroes, cards):
    state = _state(heroes)
    state.players["A"].pitch_pool = 5
    with pytest.raises(CombatError, match="não é um item"):
        use_item_token(state, "A", "Might", cards)


# --- Triggers: start_turn ---


def test_might_trigger_start_turn(heroes):
    state = _state(heroes)
    create_token(state, "A", "Might")
    notices = start_turn(state, "A")
    assert any("Might" in n.text for n in notices)
    assert "Might" not in state.players["A"].auras


def test_vigor_trigger_start_turn(heroes):
    state = _state(heroes)
    state.players["A"].pitch_pool = 0
    create_token(state, "A", "Vigor")
    notices = start_turn(state, "A")
    assert any("Vigor" in n.text for n in notices)
    assert state.players["A"].pitch_pool == 1


def test_agility_trigger_start_turn(heroes):
    state = _state(heroes)
    create_token(state, "A", "Agility")
    notices = start_turn(state, "A")
    assert any("Agility" in n.text for n in notices)
    assert "Agility" not in state.players["A"].auras


def test_toughness_trigger_opponent_start(heroes):
    state = _state(heroes)
    create_token(state, "B", "Toughness")
    # Turno de A: Toughness do B deve triggerar (início do turno do oponente)
    notices = start_turn(state, "A")
    assert any("Toughness" in n.text for n in notices)
    assert "Toughness" not in state.players["B"].auras


def test_embodiment_earth_destruido_start_turn(heroes):
    """Embodiment of Earth continua sendo destruído no início do turno."""
    state = _state(heroes)
    state.players["A"].auras["Embodiment of Earth"] = [0]
    notices = start_turn(state, "A")
    assert any("Embodiment of Earth" in n.text for n in notices)


# --- Triggers: end_turn ---


def test_ponder_trigger_end_turn(heroes):
    state = _state(heroes)
    state.active_player = "A"
    create_token(state, "A", "Ponder")
    notices = end_turn(state)
    assert any("Ponder" in n.text for n in notices)
    assert "Ponder" not in state.players["A"].auras


def test_bloodrot_pox_trigger_end_turn(heroes):
    state = _state(heroes)
    state.active_player = "A"
    create_token(state, "A", "Bloodrot Pox")
    notices = end_turn(state)
    assert any("Bloodrot Pox" in n.text for n in notices)


def test_inertia_trigger_end_turn(heroes):
    state = _state(heroes)
    state.active_player = "A"
    create_token(state, "A", "Inertia")
    notices = end_turn(state)
    assert any("Inertia" in n.text for n in notices)
    assert "Inertia" not in state.players["A"].auras


def test_frostbite_trigger_end_turn(heroes):
    state = _state(heroes)
    state.active_player = "A"
    create_token(state, "A", "Frostbite")
    notices = end_turn(state)
    assert any("Frostbite" in n.text for n in notices)
    assert "Frostbite" not in state.players["A"].auras


def test_frailty_trigger_end_turn(heroes):
    state = _state(heroes)
    state.active_player = "A"
    create_token(state, "A", "Frailty")
    notices = end_turn(state)
    assert any("Frailty" in n.text for n in notices)
    assert "Frailty" not in state.players["A"].auras


def test_end_turn_muda_active_player(heroes):
    state = _state(heroes)
    state.active_player = "A"
    end_turn(state)
    assert state.active_player == "B"


# --- Triggers: check_attack_token_triggers ---


def test_courage_trigger_attack(heroes):
    from flesh_and_blood.combat import check_attack_token_triggers

    state = _state(heroes)
    create_token(state, "A", "Courage")
    notices = check_attack_token_triggers(state, "A")
    assert any("Courage" in n.text for n in notices)
    assert "Courage" not in state.players["A"].auras


def test_quicken_trigger_attack(heroes):
    from flesh_and_blood.combat import check_attack_token_triggers

    state = _state(heroes)
    create_token(state, "A", "Quicken")
    notices = check_attack_token_triggers(state, "A")
    assert any("Quicken" in n.text for n in notices)
    assert "Quicken" not in state.players["A"].auras


def test_runechant_trigger_attack(heroes):
    from flesh_and_blood.combat import check_attack_token_triggers

    state = _state(heroes)
    create_token(state, "A", "Runechant")
    notices = check_attack_token_triggers(state, "A")
    assert any("Runechant" in n.text for n in notices)
    assert "Runechant" not in state.players["A"].auras


def test_no_attack_tokens(heroes):
    from flesh_and_blood.combat import check_attack_token_triggers

    state = _state(heroes)
    notices = check_attack_token_triggers(state, "A")
    assert notices == []


# --- Triggers: play_action (Eloquence) ---


def test_eloquence_trigger_play_action(heroes, cards):
    state = _state(heroes)
    create_token(state, "A", "Eloquence")
    state.players["A"].pitch_pool = 5
    state.players["A"].hand.append("Earthlore Surge (red)")
    start_turn(state, "A")
    from flesh_and_blood.combat import play_action

    notices = play_action(state, "A", "Earthlore Surge (red)", cards)
    assert any("Eloquence" in n.text for n in notices)
    assert "Eloquence" not in state.players["A"].auras
