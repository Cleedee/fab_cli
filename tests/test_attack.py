"""Testes do planejador de ataque (burst/lethal com premissas)."""

import pytest

from fresh_and_blood.attack import plan_attack
from fresh_and_blood.carddb import load_cards
from fresh_and_blood.models import Hero, new_game

BRIAR = Hero(
    key="Briar, Warden of Thorns",
    name="Briar, Warden of Thorns",
    life=20,
    intellect=4,
    classes=("Runeblade",),
    talents=("Earth", "Lightning"),
)
ENIGMA = Hero(
    key="Enigma",
    name="Enigma",
    life=20,
    intellect=4,
    classes=("Illusionist",),
    talents=("Mystic",),
)


@pytest.fixture()
def state():
    return new_game(BRIAR, ENIGMA)


def test_buff_antes_do_ataque_e_fusao(state):
    cards = load_cards()
    a = state.players["A"]
    a.hand = ["Sizzle (red)", "Arcanic Shockwave (red)", "Snatch (red)"]
    a.action_points = 1
    plan = plan_attack(state, "A", cards)
    assert plan.sequence == ["Sizzle (red)", "Arcanic Shockwave (red)"]
    assert plan.physical == 3 + 4
    assert plan.arcane == 1  # fusão Lightning via Sizzle
    assert plan.total == 8
    assert plan.action_points_left == 0
    assert any("Snatch" in n for n in plan.notes)  # sem AP para o Snatch
    assert not plan.lethal


def test_embodiment_lightning_salva_ataque_caro(state):
    cards = load_cards()
    a = state.players["A"]
    a.hand = ["Evergreen (red)", "Path of Same Ends (yellow)"]
    a.action_points = 1
    a.pitch_pool = 1
    a.add_aura("Embodiment of Lightning")
    plan = plan_attack(state, "A", cards)
    # Path é cortado e vira pitch para pagar os {r} do Evergreen
    assert plan.sequence == ["Evergreen (red)"]
    assert plan.physical == 7
    assert plan.arcane == 0
    assert plan.pitched == ["Path of Same Ends (yellow)"]
    assert any("cortado" in n for n in plan.notes)
    assert not plan.lethal
    assert plan_attack(state, "A", cards, opponent_life=7).lethal


def test_look_tuff_paga_extra_quando_pode(state):
    cards = load_cards()
    a = state.players["A"]
    a.hand = ["Look Tuff (red)"]
    a.action_points = 1
    a.pitch_pool = 4
    plan = plan_attack(state, "A", cards)
    assert plan.physical == 8


def test_look_tuff_sem_recurso_e_cortado(state):
    cards = load_cards()
    a = state.players["A"]
    a.hand = ["Look Tuff (red)"]  # custa 4 com o {r} extra; pool 3 não cobre
    a.action_points = 1
    a.pitch_pool = 3
    plan = plan_attack(state, "A", cards)
    assert plan.physical == 0
    assert any("cortado" in n for n in plan.notes)


def test_look_tuff_custo_extra_vem_do_pitch_de_outra(state):
    cards = load_cards()
    a = state.players["A"]
    a.hand = ["Look Tuff (red)", "Sprout Strength (red)"]
    a.action_points = 1
    a.pitch_pool = 3  # Sprout (não jogado por falta de AP? tem GA -> é jogado...)
    a.action_points = 2
    plan = plan_attack(state, "A", cards)
    # Ambos jogáveis: Sprout dá +3 (tabela) e vira GA; custo total 4 <= 3+pitch próprio?
    # Sprout é jogada, então não pode virar pitch; Look Tuff paga 3+1 com pool 3 + nada.
    # Sem recursos para o extra -> corta o de menor poder (Sprout, power 0) que vira pitch.
    assert "Look Tuff (red)" in plan.sequence
    assert plan.pitched == ["Sprout Strength (red)"]


def test_shockwave_sem_fusao_nao_tem_arcano(state):
    cards = load_cards()
    a = state.players["A"]
    a.hand = ["Arcanic Shockwave (red)"]
    a.action_points = 1
    plan = plan_attack(state, "A", cards)
    assert plan.arcane == 0
    assert any("SEM fusão" in n for n in plan.notes)


def test_arma_com_lightning_ganha_bonus(state):
    cards = load_cards()
    a = state.players["A"]
    a.hand = ["Stinging Sprite (red)"]
    a.action_points = 1
    a.pitch_pool = 1
    plan = plan_attack(state, "A", cards, weapon_key="Star Fall")
    assert plan.sequence == ["Stinging Sprite (red)", "Star Fall"]
    assert plan.physical == 3 + 2  # Sprite + Star Fall potencializado
    assert plan.arcane == 1
    assert plan.total == 6
    assert plan.action_points_left == 1  # Go Again condicional devolve o AP


def test_arma_sem_lightning_fica_fraca_e_consome_ap(state):
    cards = load_cards()
    a = state.players["A"]
    a.hand = ["Snatch (red)"]
    a.action_points = 2
    a.pitch_pool = 1
    plan = plan_attack(state, "A", cards, weapon_key="Star Fall")
    assert plan.physical == 4 + 1
    assert plan.arcane == 0
    assert plan.action_points_left == 0


def test_sem_arma_informada_avisa(state):
    cards = load_cards()
    a = state.players["A"]
    a.hand = ["Snatch (red)"]
    a.action_points = 1
    plan = plan_attack(state, "A", cards)
    assert any("Sem arma informada" in n for n in plan.notes)
