"""Testes do módulo de setup inicial de partida."""

import json

import pytest
import yaml

from fresh_and_blood.carddb import load_cards
from fresh_and_blood.deck import hero_from_deck, load_decklist
from fresh_and_blood.models import new_game
from fresh_and_blood.setup import apply_setup, auto_setup, load_setup_file, setup_weapons


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


def test_auto_setup_popula_mao_e_equip(cards, decks, heroes):
    state = new_game(heroes[0], heroes[1], "A")
    auto_setup(state, decks[0], decks[1], cards, hand_size=4)
    assert len(state.players["A"].hand) == 4
    assert len(state.players["B"].hand) == 4
    assert len(state.players["A"].equipment_uses) > 0
    assert len(state.players["B"].equipment_uses) > 0
    # Arsenal não deve ser preenchido
    assert state.players["A"].arsenal is None
    assert state.players["B"].arsenal is None


def test_auto_setup_hand_size_personalizado(cards, decks, heroes):
    state = new_game(heroes[0], heroes[1], "A")
    auto_setup(state, decks[0], decks[1], cards, hand_size=2)
    assert len(state.players["A"].hand) == 2
    assert len(state.players["B"].hand) == 2


def test_apply_setup_completo(cards, decks, heroes):
    state = new_game(heroes[0], heroes[1], "A")
    setup = {
        "hands": {"A": ["Snatch (red)", "Sizzle (red)"], "B": ["Unmovable (blue)"]},
        "arsenal": {"A": "Arcanic Shockwave (red)", "B": None},
        "equipment": {"A": ["Blade Beckoner Helm"], "B": ["Blade Beckoner Boots"]},
        "pitch_pool": {"A": 1, "B": 0},
    }
    apply_setup(state, setup, cards)
    assert state.players["A"].hand == ["Snatch (red)", "Sizzle (red)"]
    assert state.players["B"].hand == ["Unmovable (blue)"]
    assert state.players["A"].arsenal == "Arcanic Shockwave (red)"
    assert state.players["B"].arsenal is None
    assert "Blade Beckoner Helm" in state.players["A"].equipment_uses
    assert "Blade Beckoner Boots" in state.players["B"].equipment_uses
    assert state.players["A"].pitch_pool == 1
    assert state.players["B"].pitch_pool == 0


def test_apply_setup_sobrescreve_pool(cards, decks, heroes):
    state = new_game(heroes[0], heroes[1], "A")
    state.players["A"].pitch_pool = 5
    apply_setup(state, {"pitch_pool": {"A": 3}}, cards)
    assert state.players["A"].pitch_pool == 3


def test_carta_inexistente_levanta_erro(cards, decks, heroes):
    state = new_game(heroes[0], heroes[1], "A")
    with pytest.raises(ValueError, match="desconhecida"):
        apply_setup(state, {"hands": {"A": ["Carta Inexistente"]}}, cards)


def test_equipamento_nao_equip_levanta_erro(cards, decks, heroes):
    state = new_game(heroes[0], heroes[1], "A")
    with pytest.raises(ValueError, match="não é um equipamento"):
        apply_setup(state, {"equipment": {"A": ["Snatch (red)"]}}, cards)


def test_lado_invalido_levanta_erro(cards, decks, heroes):
    state = new_game(heroes[0], heroes[1], "A")
    with pytest.raises(ValueError, match="lado inválido"):
        apply_setup(state, {"hands": {"Z": ["Snatch (red)"]}}, cards)


def test_pitch_negativo_levanta_erro(cards, decks, heroes):
    state = new_game(heroes[0], heroes[1], "A")
    with pytest.raises(ValueError, match="negativo"):
        apply_setup(state, {"pitch_pool": {"A": -1}}, cards)


def test_load_setup_file_json(tmp_path, cards, decks, heroes):
    data = {"hands": {"A": ["Snatch (red)"]}}
    path = tmp_path / "setup.json"
    with open(path, "w") as f:
        json.dump(data, f)
    loaded = load_setup_file(path)
    assert loaded == data


def test_load_setup_file_yaml(tmp_path, cards, decks, heroes):
    data = {"hands": {"A": ["Snatch (red)"]}}
    path = tmp_path / "setup.yaml"
    with open(path, "w") as f:
        yaml.dump(data, f)
    loaded = load_setup_file(path)
    assert loaded == data


def test_load_setup_file_nao_dict_levanta_erro(tmp_path):
    path = tmp_path / "setup.json"
    with open(path, "w") as f:
        json.dump(["lista", "invalida"], f)
    with pytest.raises(TypeError, match="dict"):
        load_setup_file(path)


def test_setup_weapons():
    setup = {"weapons": {"A": "Star Fall", "B": None}}
    result = setup_weapons(setup)
    assert result["A"] == "Star Fall"
    assert result["B"] is None


def test_setup_weapons_vazio():
    result = setup_weapons({})
    assert result["A"] is None
    assert result["B"] is None


def test_auto_setup_mao_aleatoria_sem_seed(cards, decks, heroes):
    """Sem seed, mãos devem diferir entre execuções (aleatoriedade)."""
    s1 = new_game(heroes[0], heroes[1], "A")
    s2 = new_game(heroes[0], heroes[1], "A")
    auto_setup(s1, decks[0], decks[1], cards, hand_size=4)
    auto_setup(s2, decks[0], decks[1], cards, hand_size=4)
    # Probabilidade de colisão de 4 cartas de 47 é baixíssima
    assert s1.players["A"].hand != s2.players["A"].hand


def test_auto_setup_seed_reproduz_mao(cards, decks, heroes):
    """Mesma seed -> mesma mão para ambos os jogadores."""
    s1 = new_game(heroes[0], heroes[1], "A")
    s2 = new_game(heroes[0], heroes[1], "A")
    auto_setup(s1, decks[0], decks[1], cards, hand_size=4, seed=42)
    auto_setup(s2, decks[0], decks[1], cards, hand_size=4, seed=42)
    assert s1.players["A"].hand == s2.players["A"].hand
    assert s1.players["B"].hand == s2.players["B"].hand


def test_auto_setup_seed_diferente_mao_diferente(cards, decks, heroes):
    s1 = new_game(heroes[0], heroes[1], "A")
    s2 = new_game(heroes[0], heroes[1], "A")
    auto_setup(s1, decks[0], decks[1], cards, hand_size=4, seed=1)
    auto_setup(s2, decks[0], decks[1], cards, hand_size=4, seed=2)
    assert s1.players["A"].hand != s2.players["A"].hand


def test_auto_setup_pool_expandido_por_quantidade(cards, decks, heroes):
    """O sorteio usa o pool expandido por cópias (ex.: 2x Ravenous Rabble)."""
    total = sum(decks[0].deck_pool.values())
    expanded = [k for k, q in decks[0].deck_pool.items() for _ in range(q)]
    assert len(expanded) == total
    # Com hand_size grande, pega cartas repetidas do pool expandido
    state = new_game(heroes[0], heroes[1], "A")
    auto_setup(state, decks[0], decks[1], cards, hand_size=total, seed=7)
    # Mão do tamanho pedido, mesmo com deck_pool de chaves únicas
    assert len(state.players["A"].hand) == total
    # Deve ter ao menos uma repetição (deck tem 47 cópias > chaves únicas)
    assert len(set(state.players["A"].hand)) < total
