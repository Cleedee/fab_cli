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


def test_look_tuff_sem_recurso_joga_sem_o_extra(state):
    cards = load_cards()
    a = state.players["A"]
    a.hand = ["Look Tuff (red)"]  # pool 3 cobre o custo base, mas não o {r} extra
    a.action_points = 1
    a.pitch_pool = 3
    plan = plan_attack(state, "A", cards)
    assert plan.physical == 7  # downgrade, não removeu a carta
    assert any("extra" in n for n in plan.notes)


def test_look_tuff_downgrade_em_vez_de_remover(state):
    """Quando falta {r} para o extra, o plano faz downgrade em vez de cortar o Look Tuff."""
    cards = load_cards()
    a = state.players["A"]
    # Look Tuff (cost 3, pitch 1) + Snatch (cost 0, pitch 1).
    # Pool = 3. Potencial inicial = 3 + 1 (Snatch) = 4 >= 3+1=custo c/ extra.
    # Depois de ambos no plano, pool = 3, custo sem extra = 3, cabe.
    a.hand = ["Look Tuff (red)", "Snatch (red)"]
    a.action_points = 2
    a.pitch_pool = 3
    plan = plan_attack(state, "A", cards)
    assert "Look Tuff (red)" in plan.sequence
    assert "Snatch (red)" in plan.sequence
    assert plan.physical == 7 + 4  # Look Tuff sem extra (7) + Snatch (4)
    assert any("extra" in n for n in plan.notes)


def test_buff_e_look_tuff_sao_jogados_juntos(state):
    cards = load_cards()
    a = state.players["A"]
    # Limitação documentada: o plano não troca um buff jogável por pitch para
    # pagar o {r} extra do Look Tuff (jogar ambos -> 10 supera LT sozinho -> 8).
    a.hand = ["Look Tuff (red)", "Sprout Strength (red)"]
    a.action_points = 2
    a.pitch_pool = 3
    plan = plan_attack(state, "A", cards)
    assert set(plan.sequence) == {"Look Tuff (red)", "Sprout Strength (red)"}
    assert plan.physical == 3 + 7
    assert plan.pitched == []


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
    a.action_points = 2  # Sprite não tem Go Again: 1 AP para ele, 1 para a arma
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


def test_arma_reavaliada_apos_corte_por_recurso(state):
    """Carta cara cortada por falta de recurso libera AP para a arma.

    Look Tuff (custo 3) com pool 0 não é pagável -> vira pitch da arma
    em vez de "sem AP" falso. (bug: arma era decidida antes dos cortes)
    """
    cards = load_cards()
    a = state.players["A"]
    a.hand = ["Look Tuff (red)"]
    a.action_points = 1
    a.pitch_pool = 0
    plan = plan_attack(state, "A", cards, weapon_key="Star Fall")
    assert plan.sequence == ["Star Fall"]
    assert plan.pitched == ["Look Tuff (red)"]
    assert plan.physical == 1  # Star Fall (sem Lightning)
    assert not any("sem AP" in n for n in plan.notes)


def test_pitch_cycling_preserva_azul(state):
    """Picha carta vermelha (pitch 1) antes da azul (pitch 3) para preservar recurso."""
    cards = load_cards()
    a = state.players["A"]
    # Chimera (red, cost 2, pitch 1) + Look Tuff (red, cost 3, pitch 7) +
    # Fluid Motion (blue, cost 0, pitch 3). Pool = 0.
    # Chimera entra no plano (custo 2). Look Tuff cortado → vira pitch.
    # Fix: vermelha (1) é pichada antes da azul (3).
    a.hand = ["Enigma Chimera (red)", "Look Tuff (red)", "Fluid Motion (blue)"]
    a.action_points = 2
    a.pitch_pool = 0
    plan = plan_attack(state, "A", cards)
    # A carta de menor pitch (vermelha, 1) deve aparecer primeiro na lista
    assert len(plan.pitched) >= 1
    first = cards[plan.pitched[0]]
    assert first.pitch == 1


def test_arsenal_sugerido_quando_ap_sobra(state):
    """Quando sobra AP e há cartas na mão, sugere arsenal para o próximo turno."""
    cards = load_cards()
    a = state.players["A"]
    # Snatch (attack, Go Again) + Sigil (DR, def 3). AP=2.
    # Snatch consome 1 AP (GA devolve). Sobrou 1 AP. Sigil fica na mão.
    a.hand = ["Snatch (red)", "Sigil of Suffering (red)"]
    a.action_points = 2
    a.pitch_pool = 0
    plan = plan_attack(state, "A", cards)
    assert plan.arsenal_suggestion == "Sigil of Suffering (red)"


def test_arsenal_escolhe_maior_defesa(state):
    """Dentre cartas disponíveis, escolhe a de maior defesa+pitch para arsenal."""
    cards = load_cards()
    a = state.players["A"]
    # Snatch (attack, Go Again) + Sigil (DR, def 3, pitch 1) +
    # Unmovable (DR, def 5, pitch 3). AP=2.
    # Unmovable tem maior defesa+pitch → arsenal preferido.
    a.hand = ["Snatch (red)", "Sigil of Suffering (red)", "Unmovable (blue)"]
    a.action_points = 2
    a.pitch_pool = 0
    plan = plan_attack(state, "A", cards)
    assert plan.arsenal_suggestion == "Unmovable (blue)"


def test_sem_arsenal_quando_ap_acaba(state):
    """Sem AP restante, não sugere arsenal."""
    cards = load_cards()
    a = state.players["A"]
    # Snatch (attack, sem GA) + Sigil (DR). AP=1.
    # Snatch consome o único AP. Sem AP sobrando → sem arsenal.
    a.hand = ["Snatch (red)", "Sigil of Suffering (red)"]
    a.action_points = 1
    a.pitch_pool = 0
    plan = plan_attack(state, "A", cards)
    assert plan.arsenal_suggestion is None


def test_sem_arsenal_quando_ja_ocupado(state):
    """Arsenal já ocupado → não sugere novo."""
    cards = load_cards()
    a = state.players["A"]
    a.hand = ["Snatch (red)", "Sigil of Suffering (red)"]
    a.action_points = 2
    a.pitch_pool = 0
    a.arsenal = "Sigil of Suffering (red)"
    plan = plan_attack(state, "A", cards)
    assert plan.arsenal_suggestion is None
