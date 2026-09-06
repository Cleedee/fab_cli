"""Testes do bot Enigma (Fase 5b): motor Cosmo/auras e execução de turno."""

import pytest

from flesh_and_blood import combat as cmb
from flesh_and_blood.attack import plan_enigma
from flesh_and_blood.bot import choose_bot_defense, run_bot_turn
from flesh_and_blood.carddb import load_cards
from flesh_and_blood.models import Hero, new_game

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
def cards():
    return load_cards()


@pytest.fixture()
def state(cards):
    st = new_game(BRIAR, ENIGMA)
    st.players["A"].weapons = ["Star Fall"]
    pb = st.players["B"]
    pb.weapons = ["Cosmo, Scroll of Ancestral Tapestry"]
    cmb.start_turn(st, "B")
    return st


# ── ativação do herói ────────────────────────────────────────────────────


def test_activate_hero_ability_cria_shield(state, cards):
    pb = state.players["B"]
    pb.pitch_pool = 4
    notice = cmb.activate_hero_ability(state, "B", cards)
    assert "Spectral Shield" in notice.text
    assert pb.auras["Spectral Shield"] == [1]
    assert pb.pitch_pool == 1
    assert pb.hero_ability_used


def test_activate_hero_ability_uma_vez_por_turno(state, cards):
    pb = state.players["B"]
    pb.pitch_pool = 6
    cmb.activate_hero_ability(state, "B", cards)
    with pytest.raises(cmb.CombatError):
        cmb.activate_hero_ability(state, "B", cards)


# ── ataque com aura (Cosmo) ──────────────────────────────────────────────


def test_cosmo_requer_equipamento(state, cards):
    state.players["B"].weapons = []
    state.players["B"].add_aura("Spectral Shield", 3)
    with pytest.raises(cmb.CombatError, match="Cosmo"):
        cmb.attack_with_aura(state, "B", "Spectral Shield", cards)


def test_cosmo_dano_igual_ward_e_aura_permanece(state, cards):
    pb = state.players["B"]
    pb.add_aura("Spectral Shield", 3)  # ward 4 (1 base + 3)
    link = cmb.attack_with_aura(state, "B", "Spectral Shield", cards)
    assert link.total_damage == 4
    assert state.players["A"].life == 20
    cmb.resolve_link(state, cards)
    assert state.players["A"].life == 16
    # aura atacada NÃO vai ao cemitério nem sai de jogo
    assert pb.auras.get("Spectral Shield") == [3]


def test_cosmo_primeiro_ataque_spectral_custa_zero(state, cards):
    pb = state.players["B"]
    pb.add_aura("Spectral Shield", 0)  # ward 1
    pb.pitch_pool = 1
    cmb.attack_with_aura(state, "B", "Spectral Shield", cards)
    assert pb.pitch_pool == 1  # desconto do Enigma no 1º ataque
    assert pb.spectral_attacks_this_turn == 1


def test_cosmo_aura_com_contador_ganha_go_again(state, cards):
    pb = state.players["B"]
    pb.add_aura("Spectral Shield", 2)
    cmb.attack_with_aura(state, "B", "Spectral Shield", cards)
    assert pb.action_points == 1  # Go Again manteve o AP


def test_cosmo_uma_vez_por_turno_por_aura(state, cards):
    pb = state.players["B"]
    pb.add_aura("Spectral Shield", 3)
    cmb.attack_with_aura(state, "B", "Spectral Shield", cards)
    with pytest.raises(cmb.CombatError, match="já usado"):
        cmb.attack_with_aura(state, "B", "Spectral Shield", cards)


# ── motor: Spectral Manifestations / Solitary Companion ──────────────────


def test_manifestations_cria_shield_ward4(state, cards):
    pb = state.players["B"]
    pb.hand = ["Spectral Manifestations (red)"]
    pb.pitch_pool = 2
    cmb.play_aura_engine(state, "B", "Spectral Manifestations (red)", cards)
    assert pb.auras["Spectral Shield"] == [3]
    assert pb.action_points == 1  # Go Again da carta
    assert pb.pitch_pool == 0


def test_solitary_cria_aura_e_shield(state, cards):
    pb = state.players["B"]
    pb.hand = ["Solitary Companion (red)"]
    cmb.play_aura_engine(state, "B", "Solitary Companion (red)", cards)
    assert pb.auras.get("Solitary Companion (red)") == [0]
    assert pb.auras["Spectral Shield"] == [0]
    assert pb.action_points == 0  # sem Go Again


# ── Astral Etchings ──────────────────────────────────────────────────────


def test_astral_charge_como_instant_quando_tem_shield(state, cards):
    pb = state.players["B"]
    pb.hand = ["Astral Etchings (red)"]
    pb.add_aura("Spectral Shield", 3)
    pb.pitch_pool = 1
    ap_before = pb.action_points
    cmb.astral_charge(state, "B", cards)
    assert pb.auras["Spectral Shield"] == [6]  # +3 contadores
    assert pb.action_points == ap_before  # instant não usou AP


def test_astral_charge_como_action_sem_shield(state, cards):
    pb = state.players["B"]
    pb.hand = ["Astral Etchings (red)"]
    pb.add_aura("Waxing Specter (red)", 1)  # ward 3 + 1
    pb.pitch_pool = 1
    ap_before = pb.action_points
    cmb.astral_charge(state, "B", cards)
    assert pb.auras["Waxing Specter (red)"] == [4]
    assert pb.action_points == ap_before - 1  # action gastou 1 AP


# ── instants de aura (Waxing/Waning) ─────────────────────────────────────


def test_play_instant_aura_waxing_com_contador(state, cards):
    pb = state.players["B"]
    pb.hand = ["Waxing Specter (red)"]
    pb.pitch_pool = 2
    cmb.play_instant_aura(state, "B", "Waxing Specter (red)", cards, counters_on_enter=1)
    assert pb.auras.get("Waxing Specter (red)") == [1]
    assert pb.action_points == 1  # instant não gastou AP


def test_play_instant_transcend_nao_cria_aura(state, cards):
    pb = state.players["B"]
    pb.hand = ["Homage to Ancestors (blue)"]
    cmb.play_instant_aura(state, "B", "Homage to Ancestors (blue)", cards)
    assert "Homage to Ancestors (blue)" not in pb.auras
    assert "Homage to Ancestors (blue)" in pb.graveyard


# ── plan_enigma ──────────────────────────────────────────────────────────


def test_plan_enigma_linha_coerente(state, cards):
    pb = state.players["B"]
    pb.hand = [
        "Fluid Motion (blue)",
        "Spectral Manifestations (red)",
        "Spears of Surreality (blue)",
    ]
    pb.pitch_pool = 3
    plan = plan_enigma(state, "B", cards)
    kinds = [s[0] for s in plan.steps]
    assert "play" in kinds
    assert "cosmo" in kinds
    assert kinds[-1] == "resolve"
    assert plan.physical >= 4  # ao menos o shield


# ── turno e defesa do bot ────────────────────────────────────────────────


def test_bot_turn_aplica_dano(state, cards):
    pb = state.players["B"]
    pb.hand = [
        "Fluid Motion (blue)",
        "Spectral Manifestations (red)",
        "Astral Etchings (red)",
        "Spears of Surreality (blue)",
    ]
    pb.pitch_pool = 6
    log = run_bot_turn(state, "B", cards)
    text = "\n".join(log)
    assert "Cosmo ataca" in text
    assert "Spectral Manifestations" in text
    assert state.players["A"].life < 20
    assert pb.auras.get("Spectral Shield") is not None


def test_bot_turn_nao_picha_carta_de_defesa(state, cards):
    pb = state.players["B"]
    pb.hand = [
        "Spectral Manifestations (red)",
        "Big Blue Sky (blue)",  # defesa reaction — deve permanecer se possível
        "Fluid Motion (blue)",
    ]
    pb.pitch_pool = 5
    run_bot_turn(state, "B", cards)
    assert "Big Blue Sky (blue)" in pb.hand


def test_bot_turn_generico_outro_heroi(state, cards):
    state.players["B"].hero_key = "Kayo"
    state.players["B"].hand = ["Snatch (red)"]
    state.players["B"].pitch_pool = 0
    log = run_bot_turn(state, "B", cards)
    assert state.players["A"].life < 20 or "Snatch" in " ".join(log)


def test_bot_defende_melhor_opcao(state, cards):
    # B ataca A. A (bot) defende seu próprio turno? Não: defesa é do lado
    # oposto ao atacante. Aqui B ataca e A defende (lado A é "bot").
    pa = state.players["A"]
    cmb.start_turn(state, "B")
    pa.hand = ["Rotten Remains (red)", "Rotten Remains (red)"]
    state.players["B"].add_aura("Spectral Shield", 3)
    cmb.attack_with_aura(state, "B", "Spectral Shield", cards)
    log = choose_bot_defense(state, "A", cards)
    text = "\n".join(log)
    assert "defendeu" in text or "não defende" in text
    assert state.players["A"].life == 20  # dano ainda não resolvido
