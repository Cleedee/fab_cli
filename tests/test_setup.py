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


def test_auto_setup_um_equip_por_slot(cards, decks, heroes):
    """auto_setup equipa no máximo um item por slot (Head, Chest, Arms, Legs)."""
    state = new_game(heroes[0], heroes[1], "A")
    auto_setup(state, decks[0], decks[1], cards, hand_size=4)

    def slots_ocupados(pstate):
        slots = set()
        for key in pstate.equipment_uses:
            card = cards.get(key)
            if card and card.is_equipment:
                slot = card.equipment_slot
                if slot:
                    assert slot not in slots, f"slot {slot} duplicado: {key}"
                    slots.add(slot)
        return slots

    slots_a = slots_ocupados(state.players["A"])
    slots_b = slots_ocupados(state.players["B"])
    # Briar tem Head, Chest e Legs (sem Arms); Enigma tem Head, Chest, Arms, Legs
    assert "Head" in slots_a
    assert "Chest" in slots_a
    assert "Legs" in slots_a
    assert "Head" in slots_b
    assert "Chest" in slots_b
    assert "Arms" in slots_b
    assert "Legs" in slots_b


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


def test_apply_setup_slot_conflito_levanta_erro(cards, decks, heroes):
    """apply_setup rejeita dois equipamentos no mesmo slot."""
    state = new_game(heroes[0], heroes[1], "A")
    setup = {"equipment": {"A": ["Blade Beckoner Helm", "Nullrune Hood"]}}
    with pytest.raises(ValueError, match="conflita.*slot Head"):
        apply_setup(state, setup, cards)


def test_apply_setup_slots_distintos_ok(cards, decks, heroes):
    """Equipamentos em slots diferentes são aceitos."""
    state = new_game(heroes[0], heroes[1], "A")
    setup = {
        "equipment": {"A": ["Blade Beckoner Helm", "Blossom of Spring", "Blade Beckoner Boots"]}
    }
    apply_setup(state, setup, cards)
    assert len(state.players["A"].equipment_uses) == 3


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


def test_equipment_slot_propriedade(cards):
    """equipment_slot retorna o slot correto para cada equipamento."""
    assert cards["Blade Beckoner Helm"].equipment_slot == "Head"
    assert cards["Blade Beckoner Boots"].equipment_slot == "Legs"
    assert cards["Blossom of Spring"].equipment_slot == "Chest"
    assert cards["Uphold Tradition"].equipment_slot == "Arms"
    assert cards["Star Fall"].equipment_slot is None  # arma não tem slot
    # carta não-equipamento
    assert cards["Snatch (red)"].equipment_slot is None


def test_offhand_reconhecido(cards):
    """Cartas Off-Hand são reconhecidas corretamente."""
    bastion = cards.get("Bastion of Duty")
    assert bastion is not None
    assert bastion.is_offhand
    assert bastion.is_equipment
    assert bastion.equipment_slot == "Off-Hand"
    # Arma não é Off-Hand
    assert not cards["Star Fall"].is_offhand
    # Carta normal não é Off-Hand
    assert not cards["Snatch (red)"].is_offhand


def test_apply_setup_offhand_vai_para_offhand_key(cards, heroes):
    """apply_setup coloca Off-Hand em offhand_key e equipment_uses."""
    state = new_game(heroes[0], heroes[1], "A")
    setup = {"equipment": {"A": ["Bastion of Duty"]}}
    apply_setup(state, setup, cards)
    p = state.players["A"]
    assert p.offhand_key == "Bastion of Duty"
    assert "Bastion of Duty" in p.equipment_uses


def test_apply_setup_offhand_duplicado_levanta_erro(cards, heroes):
    """apply_setup rejeita dois Off-Hand no mesmo lado."""
    state = new_game(heroes[0], heroes[1], "A")
    setup = {"equipment": {"A": ["Bastion of Duty", "Aurum Aegis"]}}
    with pytest.raises(ValueError, match="Off-Hand duplicado"):
        apply_setup(state, setup, cards)


def test_apply_setup_offhand_com_arma_2h_levanta_erro(cards, heroes):
    """apply_setup rejeita arma 2H + Off-Hand no mesmo lado."""
    state = new_game(heroes[0], heroes[1], "A")
    # Encontrar uma arma 2H no registro
    weapon_2h = None
    for k, c in cards.items():
        if c.is_weapon and "2H" in c.types:
            weapon_2h = k
            break
    assert weapon_2h is not None, "Nenhuma arma 2H encontrada no registro"
    setup = {
        "equipment": {"A": ["Bastion of Duty"]},
        "weapons": {"A": [weapon_2h]},
    }
    with pytest.raises(ValueError, match="Arma 2H não pode coexistir com Off-Hand"):
        apply_setup(state, setup, cards)


def test_auto_setup_offhand(cards, heroes):
    """auto_setup equipa Off-Hand corretamente quando há espaço."""
    from fresh_and_blood.deck import Decklist

    deck_a = Decklist(
        hero="Briar, Warden of Thorns",
        source="test",
        arena=[
            "Scepter of Pain",
            "Blossom of Spring",
            "Blade Beckoner Helm",
            "Blade Beckoner Boots",
            "Bastion of Duty",
        ],
        deck_pool={"Snatch (red)": 2, "Ravenous Rabble (red)": 2},
    )
    deck_b = Decklist(
        hero="Ira, Crimson Haze",
        source="test",
        arena=[
            "Harmonized Kodachi",
            "Blossom of Spring",
            "Blade Beckoner Helm",
            "Blade Beckoner Boots",
        ],
        deck_pool={"Snatch (red)": 2, "Ravenous Rabble (red)": 2},
    )
    state = new_game(heroes[0], heroes[1], "A")
    auto_setup(state, deck_a, deck_b, cards, hand_size=4, seed=42)
    p = state.players["A"]
    assert p.offhand_key == "Bastion of Duty"
    assert "Bastion of Duty" in p.equipment_uses
    assert "Scepter of Pain" in p.weapons


def test_auto_setup_offhand_com_arma_2h_nao_equipa(cards, heroes):
    """auto_setup não equipa Off-Hand quando arma 2H ocupa os slots."""
    from fresh_and_blood.deck import Decklist

    deck_a = Decklist(
        hero="Briar, Warden of Thorns",
        source="test",
        arena=[
            "Star Fall",
            "Blossom of Spring",
            "Blade Beckoner Helm",
            "Blade Beckoner Boots",
            "Bastion of Duty",
        ],
        deck_pool={"Snatch (red)": 2, "Ravenous Rabble (red)": 2},
    )
    deck_b = Decklist(
        hero="Ira, Crimson Haze",
        source="test",
        arena=[
            "Harmonized Kodachi",
            "Blossom of Spring",
            "Blade Beckoner Helm",
            "Blade Beckoner Boots",
        ],
        deck_pool={"Snatch (red)": 2, "Ravenous Rabble (red)": 2},
    )
    state = new_game(heroes[0], heroes[1], "A")
    auto_setup(state, deck_a, deck_b, cards, hand_size=4, seed=42)
    p = state.players["A"]
    # Star Fall é 2H; Off-Hand não deve ser equipado
    assert p.offhand_key is None
    # Mas Off-Hand ainda pode estar em equipment_uses para defesa
    assert "Bastion of Duty" in p.equipment_uses
