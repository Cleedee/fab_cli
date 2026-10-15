"""Testes da arquitetura por herói (heroes/) e do modelo de ameaça (matchup)."""

import pytest

from flesh_and_blood import combat as cmb
from flesh_and_blood import heroes as hro
from flesh_and_blood.carddb import load_cards
from flesh_and_blood.defense import suggest_defense
from flesh_and_blood.heroes.bravo import crush_threat, is_crush
from flesh_and_blood.heroes.generic import GenericStrategy
from flesh_and_blood.heroes.matchups import phantasm_risk, threat_report
from flesh_and_blood.models import Hero, new_game

BRIAR = Hero("Briar, Warden of Thorns", "Briar", 20, 4, ("Runeblade",), ())
ENIGMA = Hero("Enigma", "Enigma", 20, 4, ("Illusionist",), ("Mystic",))
BRAVO = Hero("Bravo, Flattering Showman", "Bravo", 20, 4, ("Guardian",), ())


@pytest.fixture()
def cards():
    return load_cards()


# ── registry ────────────────────────────────────────────────────────────


def test_strategy_for_despacha_por_heroi():
    assert isinstance(hro.strategy_for("Enigma"), hro.EnigmaStrategy)
    assert isinstance(hro.strategy_for("Bravo, Flattering Showman"), hro.BravoStrategy)
    # Herói sem estratégia própria cai no genérico.
    assert isinstance(hro.strategy_for("Kayo"), GenericStrategy)


def test_generic_strategy_planeja_com_arma(cards):
    st = new_game(BRIAR, ENIGMA)
    a = st.players["A"]
    a.weapons = ["Star Fall"]
    a.hand = ["Snatch (red)"]
    a.pitch_pool = 1
    plan = hro.strategy_for("Briar, Warden of Thorns").plan_turn(st, "A", cards)
    kinds = [s[0] for s in plan.steps]
    assert "resolve" in kinds
    assert plan.physical > 0
    assert "Snatch (red)" in plan.sequence


# ── modelo de ameaça do Bravo (crush) ────────────────────────────────────


def test_is_crush():
    cards = load_cards()
    assert is_crush(cards["Chokeslam (red)"])
    assert not is_crush(cards["Snatch (red)"])


def test_crush_threat_estima_dominate_com_recursos(cards):
    st = new_game(ENIGMA, BRAVO)
    b = st.players["B"]
    b.arsenal = "Chokeslam (red)"  # 8{p}, custo 4
    b.hand = ["Boulder Drop (blue)", "Chokeslam (blue)"]  # 2 blues = 6{r}
    threat = crush_threat(b, cards)
    assert threat is not None
    assert threat.card_key == "Chokeslam (red)"
    assert threat.power == 10  # 8 + 2 da habilidade do herói
    assert threat.dominate is True
    assert threat.ready is True
    assert "4 or more" in threat.effect


def test_crush_threat_none_sem_crush_no_arsenal(cards):
    st = new_game(ENIGMA, BRAVO)
    b = st.players["B"]
    b.arsenal = "Snatch (red)"
    assert crush_threat(b, cards) is None


def test_bravo_strategy_anota_crush_no_arsenal(cards):
    st = new_game(ENIGMA, BRAVO)
    b = st.players["B"]
    b.arsenal = "Boulder Drop (red)"
    b.hand = ["Snatch (red)"]
    plan = hro.strategy_for("Bravo, Flattering Showman").plan_turn(st, "B", cards)
    assert any("crush" in n for n in plan.notes)


# ── risco de Phantasm (leitura de mesa) ──────────────────────────────────


def test_phantasm_risk_detecta_attack_action_grande(cards):
    st = new_game(ENIGMA, BRAVO)
    b = st.players["B"]
    b.hand = ["Chokeslam (blue)"]  # 6{p}, não-Illusionist
    assert phantasm_risk(b, cards) == "Chokeslam (blue)"


def test_phantasm_risk_ignora_cartas_pequenas_e_illusionist(cards):
    st = new_game(ENIGMA, BRAVO)
    b = st.players["B"]
    b.hand = ["Snatch (red)", "Enigma Chimera (blue)"]  # 4{p} e Illusionist
    assert phantasm_risk(b, cards) is None


# ── plano do Enigma reage ao risco de Phantasm ───────────────────────────


def test_enigma_evita_phantasm_com_risco(cards):
    st = new_game(ENIGMA, BRAVO)
    a = st.players["A"]
    a.weapons = ["Cosmo, Scroll of Ancestral Tapestry"]
    a.hand = ["Enigma Chimera (red)", "Snatch (red)"]  # 8{p} phantasm | 4{p}
    a.pitch_pool = 2
    a.hero_ability_used = True
    cmb.start_turn(st, "A")
    a.hero_ability_used = True
    # Bravo guarda um 6{p} não-Illusionist → Chimera é frágil.
    st.players["B"].hand = ["Chokeslam (blue)"]

    plan = hro.strategy_for("Enigma").plan_turn(st, "A", cards)
    attacks = [s[1] for s in plan.steps if s[0] == "attack"]
    assert "Enigma Chimera (red)" not in attacks
    assert "Snatch (red)" in attacks


def test_enigma_usa_phantasm_sem_risco(cards):
    st = new_game(ENIGMA, BRAVO)
    a = st.players["A"]
    a.weapons = ["Cosmo, Scroll of Ancestral Tapestry"]
    a.hand = ["Enigma Chimera (red)", "Snatch (red)"]
    a.pitch_pool = 2
    cmb.start_turn(st, "A")
    a.hero_ability_used = True
    st.players["B"].hand = []  # sem popper

    plan = hro.strategy_for("Enigma").plan_turn(st, "A", cards)
    # Sem risco, o ataque de maior poder (Chimera 8) é preferido.
    attacks = [s[1] for s in plan.steps if s[0] == "attack"]
    assert "Enigma Chimera (red)" in attacks


# ── valor de mão específico do herói (defesa) ───────────────────────────


def test_enigma_hand_value_bonus_preserva_motor(cards):
    strat = hro.strategy_for("Enigma")
    assert strat.hand_value_bonus(cards["Spectral Manifestations (red)"]) == 6.0
    assert strat.hand_value_bonus(cards["Astral Etchings (red)"]) == 5.0
    assert strat.hand_value_bonus(cards["Unflinching Foothold"]) == 5.0
    assert strat.hand_value_bonus(cards["Snatch (red)"]) == 0.0


def test_value_bonus_evita_gastar_charge_na_defesa(cards):
    hand = {k: cards[k] for k in ["Astral Etchings (red)", "Snatch (red)"]}
    # Sem bônus, Astral Etchings (def 3, valor baixo) é o bloco mais barato.
    sem = suggest_defense(2, hand)
    assert "Astral Etchings (red)" in sem[0].hand_cards
    # Com o bônus do Enigma, o charge é preservado e o Snatch bloqueia.
    com = suggest_defense(2, hand, value_bonus=hro.strategy_for("Enigma").hand_value_bonus)
    assert "Astral Etchings (red)" not in com[0].hand_cards
    assert "Snatch (red)" in com[0].hand_cards


def test_threat_report_lista_crush_e_phantasm(cards):
    st = new_game(ENIGMA, BRAVO)
    b = st.players["B"]
    b.arsenal = "Chokeslam (red)"
    b.hand = ["Boulder Drop (blue)", "Boulder Drop (blue)", "Chokeslam (blue)"]
    lines = "\n".join(threat_report(st, "A", cards))
    assert "crush" in lines
    assert "PHANTASM" in lines
