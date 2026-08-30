"""Testes da passiva watery grave do Gravy Bones (jogar cartas do cemitério)."""

import pytest

from flesh_and_blood.app import _parse_grave_source
from flesh_and_blood.carddb import load_cards
from flesh_and_blood.combat import (
    CombatError,
    declare_attack,
    discard,
    may_play_from_graveyard,
    play_action,
    start_turn,
)
from flesh_and_blood.models import Hero, new_game


@pytest.fixture(scope="module")
def cards():
    return load_cards()


@pytest.fixture()
def state():
    gravy = Hero("Gravy Bones", "Gravy Bones", 20, 4, ("Pirate", "Necromancer"), ())
    enemy = Hero("Enigma", "Enigma", 20, 4, ("Illusionist",), ())
    return new_game(gravy, enemy, "A")


def _enable(state, cards, side="A", blue_key="Sink Below (blue)"):
    p = state.players[side]
    p.hand.append(blue_key)
    discard(state, side, blue_key, cards)


# --- Card.is_watery_grave ---


def test_watery_grave_detectado_no_texto(cards):
    assert cards["Angry Bones (blue)"].is_watery_grave


def test_nao_watery_grave(cards):
    assert not cards["Sink Below (blue)"].is_watery_grave


# --- discard: condição do blue ---


def test_discard_blue_habilita_condicao(state, cards):
    _enable(state, cards)
    assert state.players["A"].blue_to_graveyard_this_turn == 1


def test_discard_nao_blue_nao_habilita(state, cards):
    state.players["A"].hand.append("Jittery Bones (red)")
    discard(state, "A", "Jittery Bones (red)", cards)
    assert state.players["A"].blue_to_graveyard_this_turn == 0


def test_discard_sem_cards_dict_nao_detecta_blue(state):
    state.players["A"].hand.append("Sink Below (blue)")
    discard(state, "A", "Sink Below (blue)")  # sem o registry
    assert state.players["A"].blue_to_graveyard_this_turn == 0


# --- may_play_from_graveyard ---


def test_negado_sem_blue_no_cemiterio(state):
    assert not may_play_from_graveyard(state, "A")


def test_liberado_apos_blue_descartado(state, cards):
    _enable(state, cards)
    assert may_play_from_graveyard(state, "A")


def test_negado_para_heroi_sem_passiva(state, cards):
    _enable(state, cards, side="A")
    assert not may_play_from_graveyard(state, "B")


def test_condicao_resetada_no_start_turn(state, cards):
    _enable(state, cards)
    start_turn(state, "A")
    assert state.players["A"].blue_to_graveyard_this_turn == 0
    assert not may_play_from_graveyard(state, "A")


# --- play_action do cemitério ---


def test_play_do_cemiterio_ok(state, cards):
    _enable(state, cards)
    state.players["A"].graveyard.append("Give No Quarter (blue)")
    notices = play_action(state, "A", "Give No Quarter (blue)", cards, source="graveyard")
    assert any("cemitério" in n.text for n in notices)
    assert "Give No Quarter (blue)" not in state.players["A"].graveyard
    assert state.players["A"].non_attack_actions_played == 1


def test_play_do_cemiterio_sem_condicao_erro(state, cards):
    state.players["A"].graveyard.append("Give No Quarter (blue)")
    with pytest.raises(CombatError, match="Gravy Bones"):
        play_action(state, "A", "Give No Quarter (blue)", cards, source="graveyard")


def test_play_do_cemiterio_carta_sem_watery_grave_erro(state, cards):
    _enable(state, cards)
    state.players["A"].graveyard.append("Aether Arc (blue)")
    with pytest.raises(CombatError, match="watery grave"):
        play_action(state, "A", "Aether Arc (blue)", cards, source="graveyard")


def test_play_do_cemiterio_carta_nao_esta_la_erro(state, cards):
    _enable(state, cards)
    state.players["A"].hand.append("Give No Quarter (blue)")
    with pytest.raises(CombatError, match="cemitério"):
        play_action(state, "A", "Give No Quarter (blue)", cards, source="graveyard")


def test_play_da_mao_continua_ok(state, cards):
    state.players["A"].hand.append("Give No Quarter (blue)")
    play_action(state, "A", "Give No Quarter (blue)", cards)
    assert state.players["A"].graveyard == []
    assert "Give No Quarter (blue)" not in state.players["A"].hand


# --- declare_attack do cemitério ---


def test_attack_do_cemiterio_ok(state, cards):
    _enable(state, cards)
    state.players["A"].graveyard.append("Angry Bones (blue)")
    state.players["A"].pitch_pool = 3
    link = declare_attack(state, "A", "Angry Bones (blue)", cards, source="graveyard")
    assert link.card_key == "Angry Bones (blue)"
    assert "Angry Bones (blue)" not in state.players["A"].graveyard
    assert state.players["A"].pitch_pool == 1  # custo 2


def test_attack_do_cemiterio_sem_condicao_erro(state, cards):
    state.players["A"].graveyard.append("Angry Bones (blue)")
    with pytest.raises(CombatError, match="Gravy Bones"):
        declare_attack(state, "A", "Angry Bones (blue)", cards, source="graveyard")


def test_arma_nao_sai_do_cemiterio(state, cards):
    with pytest.raises(CombatError, match="armas"):
        declare_attack(state, "A", "Star Fall", cards, is_weapon=True, source="graveyard")


# --- _parse_grave_source ---


def test_parse_source_default_hand():
    source, rest = _parse_grave_source(["Snatch (red)"])
    assert source == "hand"
    assert rest == ["Snatch (red)"]


def test_parse_source_graveyard():
    source, rest = _parse_grave_source(["Give No Quarter (blue)", "from=graveyard"])
    assert source == "graveyard"
    assert rest == ["Give No Quarter (blue)"]


def test_parse_source_grave_abreviado():
    source, rest = _parse_grave_source(["from=grave", "Give No Quarter (blue)"])
    assert source == "graveyard"
    assert rest == ["Give No Quarter (blue)"]


def test_parse_source_invalido():
    with pytest.raises(ValueError, match="origem inválida"):
        _parse_grave_source(["from=banished"])
