#!/usr/bin/env python3
"""Simulação de matchup Enigma (Colin Li) vs Bravo, Flattering Showman.

Uso:
    python scripts/sim_enigma_vs_bravo.py

Cenários (o motor não modela o turno do Bravo; o crush é injetado como ChainLink):

    A) Ameaça de crush estimada (arsenal + habilidade do herói = 10{p} Dominate)
       e as opções de defesa do Enigma — com e sem o truque do Unflinching
       Foothold (remove Dominate -> volta a bloquear com várias cartas).
    B) Turno do Enigma: com Phantasm sob risco (Bravo guarda 6{p}) o plano evita
       Enigma Chimera/Spears; sem risco, usa o ataque de maior poder.
    C) Matemática do ward: quanto uma aura Spectral Shield previne e como manter
       o dano do crush < 4 (desliga o crush).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from flesh_and_blood import combat
from flesh_and_blood.carddb import load_cards
from flesh_and_blood.combat import aura_attack_power, spend_ward, ward_value
from flesh_and_blood.defense import suggest_defense
from flesh_and_blood.heroes import crush_threat, plan_enigma, strategy_for, ward_base
from flesh_and_blood.models import Hero, new_game

ENIGMA_EQUIPMENT = [
    "Blade Beckoner Helm",
    "Blade Beckoner Plating",
    "Unflinching Foothold",
]
COSMO = "Cosmo, Scroll of Ancestral Tapestry"


def make_state():
    """Estado base: Enigma (A) vs Bravo (B); arma e equipamento do Enigma."""
    enigma = Hero("Enigma", "Enigma", 20, 4, ("Illusionist",), ("Mystic",))
    bravo = Hero("Bravo, Flattering Showman", "Bravo", 20, 4, ("Guardian",), ())
    state = new_game(enigma, bravo, first_player="A")
    a = state.players["A"]
    a.weapons = [COSMO]
    a.equipment_uses = dict.fromkeys(ENIGMA_EQUIPMENT)
    return state


def _equip_defense(state, cards, side):
    p = state.players[side]
    return {
        k: (cards[k].defense or 0)
        for k in p.equipment_uses
        if k not in p.equipment_destroyed
        and k not in p.equipment_used_this_turn
        and cards[k].is_equipment
        and (cards[k].defense or 0) > 0
    }


def scenario_crush_defense(cards):
    print("=" * 72)
    print("A) TURNO DE CRUSH DO BRAVO (10{p} Dominate) — defesa do Enigma")
    print("=" * 72)
    state = make_state()
    b = state.players["B"]
    b.arsenal = "Chokeslam (red)"
    b.hand = ["Boulder Drop (blue)", "Chokeslam (blue)"]

    threat = crush_threat(b, cards)
    print(f"Arsenal: {b.arsenal}; mão: {', '.join(b.hand)}")
    print(f"-> Ameaça: {threat.power}{{p}} Dominate; crush: {threat.effect}")
    print()

    a = state.players["A"]
    a.hand = [
        "Test of Strength (red)",  # 4{d}
        "Big Blue Sky (blue)",  # 2{d} (+1 por blue pitchado)
        "Spectral Manifestations (red)",  # def 2 — MOTOR, não gastar
        "Clear Conscience (red)",  # 3{d}
    ]
    value_bonus = strategy_for("Enigma").hand_value_bonus
    hand = {k: cards[k] for k in a.hand if k in cards}
    equip = _equip_defense(state, cards, "A")

    print("Mão:", ", ".join(a.hand))
    print(f"Equip: {equip}")
    print("Opções do sugeridor (Dominate ligado — máx. 1 action card):")
    for opt in suggest_defense(
        threat.power, hand, equip, dominate=True, top=3, value_bonus=value_bonus
    ):
        print(
            f"    dano={opt.damage_taken:>2}  bloqueio={opt.block_total:>2}  "
            f"mão={list(opt.hand_cards)}  equip={list(opt.equipment)}"
        )
    print()
    print("Truque Unflinching Foothold: Instant - Destroy: o ataque perde Dominate.")
    print("Sem Dominate, várias cartas da mão podem defender:")
    for opt in suggest_defense(
        threat.power, hand, equip, dominate=False, top=3, value_bonus=value_bonus
    ):
        print(
            f"    dano={opt.damage_taken:>2}  bloqueio={opt.block_total:>2}  "
            f"mão={list(opt.hand_cards)}  equip={list(opt.equipment)}"
        )
    print("=> Sobreviver ao turno de crush é o objetivo; mantenha < 4 para")
    print("   DESLIGAR o efeito de crush (CR 8.4.2a).")
    print()


def scenario_enigma_turn(cards):
    print("=" * 72)
    print("B) TURNO DO ENIGMA — Phantasm sob risco vs sem risco")
    print("=" * 72)
    hand = ["Enigma Chimera (red)", "Snatch (red)"]

    for risk, opp_hand in (
        ("COM risco (Bravo guarda Chokeslam 6{p})", ["Chokeslam (blue)"]),
        ("SEM risco (Bravo sem 6{p} na mão)", []),
    ):
        state = make_state()
        a = state.players["A"]
        a.hand = list(hand)
        a.pitch_pool = 2
        combat.start_turn(state, "A")
        a.hero_ability_used = True
        state.players["B"].hand = list(opp_hand)
        plan = plan_enigma(state, "A", cards)
        attacks = [s[1] for s in plan.steps if s[0] == "attack"]
        print(f"{risk}:")
        print(f"    ataques escolhidos: {attacks}  (dano {plan.physical})")
        for n in plan.notes:
            if "PHANTASM" in n:
                print(f"    nota: {n}")
    print("=> Enigma Chimera/Spears (Phantasm) podem ser destruídas por um attack")
    print("   action não-Illusionist de 6+{p} do Bravo. Prefira Clear Conscience")
    print("   e ataques de aura via Cosmo (imunes).")
    print()


def scenario_ward_math(cards):
    print("=" * 72)
    print("C) WARD: prevenção (destaque) vs poder de ataque (contadores)")
    print("=" * 72)
    print("CR 8.3.20: destruir a aura previne o ward BASE. Contadores +1{p}")
    print("NÃO aumentam a prevenção — só o ataque do Cosmo (base + contadores).")
    shield = cards["Spectral Shield"]
    print(f"\n    Spectral Shield: ward base {ward_base(shield)} (CR 8.3.21).")

    state = make_state()
    a = state.players["A"]
    a.add_aura("Spectral Shield", counters=5)  # cara: vale para o ataque
    a.add_aura("Spectral Shield", counters=0)  # barata: sacrifica primeiro
    prevention = ward_value(a, "Spectral Shield", shield)
    attack = aura_attack_power(a, "Spectral Shield", shield)
    print(
        f"    2 shields -> ward_value = {prevention} (preventável); "
        f"ataque do Cosmo = {attack}{{p}}."
    )
    notices = spend_ward(state, "A", "Spectral Shield", needed=1, cards=cards)
    for n in notices:
        print(f"      {n.text}")
    print(f"    cópia preservada para o ataque: {a.auras['Spectral Shield']}")
    print("    => Prevenção = nº de auras destruídas x 1; acumule shields.")
    print()
    example = [
        "10 (crush) - 4 (Test of Strength) - 1 (Helm) - 1 (Plating) = 4 -> crush DISPARA",
        "10 (crush) - 4 (Test of Strength) - 4 (4 shields destruídos) = 2 -> crush desligado",
        "10 (crush) - 4 (Test of Strength) - 1 (equip) - 5 (Moon Chakra transcendido) = 0",
    ]
    print("    Exemplos de linha (Dominate: só 1 carta da mão):")
    for line in example:
        print(f"      {line}")
    print()


def main() -> None:
    cards = load_cards()
    print()
    print("Enigma (Cosmo/auras) vs Bravo (Guardian crush) — Silver Age")
    print("Deck do Enigma: data/decks/enigma_colin_li.yaml")
    print("Deck do Bravo:   data/decks/bravo_atlanta_2nd.yaml")
    print()
    scenario_crush_defense(cards)
    scenario_enigma_turn(cards)
    scenario_ward_math(cards)


if __name__ == "__main__":
    main()
