"""Testes de prioridade formal, reactions e draw do deck (Fase 5c)."""

import pytest

from flesh_and_blood import combat as cmb
from flesh_and_blood.bot import run_bot_turn
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
    st.players["B"].weapons = ["Cosmo, Scroll of Ancestral Tapestry"]
    cmb.start_turn(st, "A")
    return st


def play_attack(state, cards, side="A", key="Ravenous Rabble (red)"):
    """Helper: declara ataque com a carta escolhida (hand preparada)."""
    p = state.players[side]
    p.hand.append(key)
    p.pitch_pool = 5
    return cmb.declare_attack(state, side, key, cards)


# ── prioridade ────────────────────────────────────────────────────────────


def test_prioridade_inicial_eh_primeiro_jogador(cards):
    st = new_game(BRIAR, ENIGMA)
    assert st.priority == "A"
    assert st.passes == 0


def test_start_turn_seta_prioridade(state):
    assert state.active_player == "A"
    assert state.priority == "A"


def test_give_priority_transfere_e_zeres_passes(state):
    state.passes = 1
    cmb.give_priority(state, "B")
    assert state.priority == "B"
    assert state.passes == 0


def test_primeiro_pass_devolve_ao_oponente_sem_resolver(state, cards):
    link = play_attack(state, cards)
    cmb.pass_priority(state, "A", cards)
    assert state.priority == "B"
    assert state.passes == 1
    assert not link.resolved


def test_segundo_pass_resolve_o_topo(state, cards):
    link = play_attack(state, cards)
    cmb.pass_priority(state, "A", cards)
    notices = cmb.pass_priority(state, "B", cards)
    assert link.resolved
    assert state.priority == "A"
    assert state.passes == 0
    texts = [n.text for n in notices]
    assert any("resolveu" in t.lower() for t in texts) or any(
        "resolvido" in t.lower() for t in texts
    )


def test_pass_fora_da_prioridade_da_aviso_mas_conta(state, cards):
    play_attack(state, cards)
    notices = cmb.pass_priority(state, "B", cards)  # prioridade é de A
    assert any("Aviso" in n.text for n in notices)
    assert state.passes == 1
    assert state.priority == "A"


def test_dois_passes_sem_link_apenas_fecham_janela(state):
    cmb.pass_priority(state, "A", {})
    assert state.passes == 1
    cmb.pass_priority(state, "B", {})
    assert state.passes == 0
    assert state.priority == "A"


# ── reactions ─────────────────────────────────────────────────────────────


def test_defense_reaction_bloqueia_sem_ap_sem_quebrar_corrente(state, cards):
    link = play_attack(state, cards)
    ap_before = state.players["A"].action_points
    pb = state.players["B"]
    pb.hand.append("Evasive Leap (red)")  # Defense Reaction genérica, defesa 3
    notices = cmb.play_reaction(state, "B", "Evasive Leap (red)", cards)
    assert link.blocked_damage == 3
    assert link.responses == [("B", "Evasive Leap (red)")]
    assert "Evasive Leap (red)" in pb.graveyard
    # sem gasto de AP e corrente intacta (elo continua aberto)
    assert state.players["A"].action_points == ap_before
    assert not link.resolved
    assert any("defendeu" in n.text for n in notices)


def test_attack_reaction_aumenta_poder_do_link(state, cards):
    link = play_attack(state, cards)
    pa = state.players["A"]
    pa.hand.append("Razor Reflex (red)")  # Attack Reaction (efeito não modelado)
    notices = cmb.play_reaction(state, "A", "Razor Reflex (red)", cards)
    assert link.responses == [("A", "Razor Reflex (red)")]
    assert any("não modelado" in n.text for n in notices)
    assert "Razor Reflex (red)" in pa.graveyard


def test_instant_generico_vai_ao_cemiterio_e_registra_resposta(state, cards):
    link = play_attack(state, cards)
    pb = state.players["B"]
    pb.hand.append("Brush Off (red)")  # Instant genérico
    notices = cmb.play_reaction(state, "B", "Brush Off (red)", cards)
    assert link.responses == [("B", "Brush Off (red)")]
    assert "Brush Off (red)" in pb.graveyard
    assert any("não modelado" in n.text for n in notices)


def test_instant_aura_entra_como_aura_e_registra_resposta(state, cards):
    link = play_attack(state, cards)
    pb = state.players["B"]
    pb.hand.append("Waxing Specter (red)")
    pb.pitch_pool = 5
    notices = cmb.play_reaction(state, "B", "Waxing Specter (red)", cards)
    assert link.responses == [("B", "Waxing Specter (red)")]
    assert pb.auras["Waxing Specter (red)"] == [0]
    assert any("aura" in n.text for n in notices)


def test_play_reaction_rejeita_nao_reaction(state, cards):
    play_attack(state, cards)
    state.players["B"].hand.append("Ravenous Rabble (red)")
    with pytest.raises(cmb.CombatError, match="reaction nem instant"):
        cmb.play_reaction(state, "B", "Ravenous Rabble (red)", cards)


def test_play_reaction_exige_carta_na_mao(state, cards):
    play_attack(state, cards)
    with pytest.raises(cmb.CombatError, match="não está na mão"):
        cmb.play_reaction(state, "B", "Evasive Leap (red)", cards)


def test_reaction_sem_ap_mas_com_custo(state, cards):
    link = play_attack(state, cards)
    pb = state.players["B"]
    pb.hand.append("Rise Above (red)")  # DR custo 2, defesa 4
    pb.pitch_pool = 1
    with pytest.raises(cmb.CombatError, match="recursos insuficientes"):
        cmb.play_reaction(state, "B", "Rise Above (red)", cards)
    pb.pitch_pool = 3
    notices = cmb.play_reaction(state, "B", "Rise Above (red)", cards)
    assert link.blocked_damage == 4
    assert pb.pitch_pool == 1
    assert any("defendeu" in n.text for n in notices)


# ── draw do deck ──────────────────────────────────────────────────────────


def test_draw_from_deck_compra_o_topo(state):
    pb = state.players["B"]
    pb.deck = ["X (red)", "Y (blue)", "Z (yellow)"]
    notice = cmb.draw_from_deck(state, "B")
    assert "X (red)" in notice.text
    assert pb.hand == ["X (red)"]
    assert pb.deck == ["Y (blue)", "Z (yellow)"]


def test_draw_from_deck_vazio_erro(state):
    state.players["B"].deck = []
    with pytest.raises(cmb.CombatError, match="deck vazio"):
        cmb.draw_from_deck(state, "B")


def test_auto_setup_deixa_resto_no_deck(cards):
    from pathlib import Path

    from flesh_and_blood.deck import load_decklist
    from flesh_and_blood.setup import auto_setup

    deck_path = Path("data/decks/enigma_colin_li.yaml")
    if not deck_path.exists():
        pytest.skip("decklist de Enigma indisponível")
    dl = load_decklist(deck_path)
    st = new_game(BRIAR, ENIGMA)
    auto_setup(st, dl, dl, cards, hand_size=4, seed=42)
    pb = st.players["B"]
    assert len(pb.hand) == 4
    assert len(pb.deck) == sum(dl.deck_pool.values()) - 4
    assert len(pb.hand) + len(pb.deck) == sum(dl.deck_pool.values())


# ── persistência / bot ────────────────────────────────────────────────────


def test_save_load_preserva_prioridade_passes_deck_e_responses(state, cards):
    play_attack(state, cards)
    state.players["B"].hand.append("Evasive Leap (red)")
    cmb.play_reaction(state, "B", "Evasive Leap (red)", cards)
    state.players["A"].deck = ["A (red)"]
    cmb.pass_priority(state, "A", cards)
    restored = new_game(BRIAR, ENIGMA).from_dict(state.to_dict())
    assert restored.priority == "B"
    assert restored.passes == 1
    assert restored.players["A"].deck == ["A (red)"]
    assert restored.chain[0].responses == [("B", "Evasive Leap (red)")]


def test_bot_passa_prioridade_ao_fim_do_turno(state, cards):
    pb = state.players["B"]
    pb.hand = ["Spectral Manifestations (red)", "Fluid Motion (blue)"]
    pb.pitch_pool = 0
    pb.weapons = ["Cosmo, Scroll of Ancestral Tapestry"]
    cmb.start_turn(state, "B")
    run_bot_turn(state, "B", cards)
    assert state.priority == "A"
