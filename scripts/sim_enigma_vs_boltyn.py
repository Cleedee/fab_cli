#!/usr/bin/env python3
"""Simulação de matchup Enigma (Colin Li) vs Boltyn (precon Silver Age).

Uso:
    python scripts/sim_enigma_vs_boltyn.py

Cenários (o motor não modela o Boltyn; cada ataque dele é injetado como ChainLink):

    A) Turno do Boltyn "carregado" (Valiant Thrust 7, Take Flight 4, Raydn 3)
       e as opções de defesa do Enigma — aplicando MANUALMENTE o +1{p} que a
       habilidade do herói dá a ataques bloqueados por attack action card.
    B) Turno da Enigma (plan_enigma + run_bot_turn).
    C) Phantasm: Enigma Chimera (6) é destruída se o Boltyn defender com
       Valiant Thrust (red) carregado (7, attack action não-Illusionist 6+);
       ataques de aura via Cosmo são imunes.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from flesh_and_blood import combat
from flesh_and_blood.attack import plan_enigma
from flesh_and_blood.bot import run_bot_turn
from flesh_and_blood.carddb import load_cards
from flesh_and_blood.defense import suggest_defense
from flesh_and_blood.models import ChainLink, Hero, new_game

ENIGMA_EQUIPMENT = [
    "Blade Beckoner Helm",
    "Blade Beckoner Plating",
    "Uphold Tradition",
    "Silent Stilettos",
]
COSMO = "Cosmo, Scroll of Ancestral Tapestry"


def make_state():
    """Estado base: Enigma (A) vs Boltyn (B), equipamento e arma do Enigma."""
    enigma = Hero(key="Enigma", name="Enigma", life=20, intellect=4,
                  classes=("Illusionist",), talents=("Mystic",))
    boltyn = Hero(key="Boltyn", name="Boltyn", life=20, intellect=4,
                  classes=("Light", "Warrior"), talents=())
    state = new_game(enigma, boltyn, first_player="A")
    a = state.players["A"]
    a.weapons = [COSMO]
    a.equipment_uses = list(ENIGMA_EQUIPMENT)
    return state


def _is_attack_action(cards, key):
    card = cards.get(key)
    return card is not None and "Attack" in card.types and "Action" in card.types


def scenario_boltyn_turn(cards):
    """A) Turno do Boltyn carregado: 7 + 4 + 3, Enigma defende."""
    print("=" * 72)
    print("A) TURNO DO BOLTYN (carregado) — defesa do Enigma")
    print("=" * 72)
    state = make_state()
    a = state.players["A"]
    a.hand = [
        "Test of Strength (red)",
        "On the Horizon (red)",
        "Springboard Somersault (yellow)",
        "Big Blue Sky (blue)",
        "Clear Conscience (red)",
    ]
    combat.start_turn(state, "B")
    print("Mão da Enigma:", ", ".join(a.hand))
    print()

    wave = [("Valiant Thrust (red)", 7), ("Take Flight (red)", 4),
            ("Raydn, Duskbane", 3)]
    for name, power in wave:
        hand = {k: cards[k] for k in a.hand if k in cards}
        equip = {
            k: (cards[k].defense or 0)
            for k in a.equipment_uses
            if k not in a.equipment_destroyed
            and k not in a.equipment_used_this_turn
            and cards[k].is_equipment
            and (cards[k].defense or 0) > 0
        }
        options = suggest_defense(power, hand, equip, top=3)
        print(f"{name} ({power}p) — opções do sugeridor:")
        for opt in options:
            print(f"    defesa {opt.block_total}: cartas={list(opt.hand_cards)}, "
                  f"equip={list(opt.equipment)}")
        best, bad = options[0], options[-1]
        # +1{p} se qualquer carta usada for attack action (habilidade do herói).
        penalty_best = 1 if any(_is_attack_action(cards, k) for k in best.hand_cards) else 0
        penalty_bad = 1 if any(_is_attack_action(cards, k) for k in bad.hand_cards) else 0
        link = ChainLink(attacker="B", card_key=name, total_damage=power)
        state.chain.append(link)
        for k in best.hand_cards:
            combat.defend_link(state, "A", [k], cards)
        for eq in best.equipment:
            combat.use_equipment_defense(state, "A", eq, cards)
        result = combat.resolve_link(state, cards)
        net = power + penalty_best - best.block_total
        a.life -= max(0, net)
        print(f"    => jogou {list(best.hand_cards) or 'só equipamento'} "
              f"(bloqueou {best.block_total}); dano real {max(0, net)}")
        diff = best.block_total - bad.block_total
        print(f"    pior opção ({list(bad.hand_cards) or list(bad.equipment)}) "
              f"bloquearia {bad.block_total} (dif. {diff:+d})")
        print()
    print("Regra aplicada: se o bloqueio usasse attack action card, cada ataque")
    print("ganharia +1{p} (habilidade do herói) — por isso 'Clear Conscience' (3{d})\n")
    print("só é bloqueio se a 7 for excedente; nas opções boas o +1 não entra.")
    print()


def scenario_enigma_turn(cards):
    """B) Turno da Enigma com abertura de motor."""
    print("=" * 72)
    print("B) TURNO DA ENIGMA — abertura de motor")
    print("=" * 72)
    state = make_state()
    state.players["A"].hand = [
        "Spectral Manifestations (red)",
        "Astral Etchings (red)",
        "Solitary Companion (red)",
        "Clear Conscience (red)",
        "Enigma Chimera (blue)",
    ]
    plan = plan_enigma(state, "A", cards)
    print("Mão:", ", ".join(state.players["A"].hand))
    print("Plano:", plan.steps)
    print(f"Dano físico estimado: {plan.physical} | pitched: {plan.pitched}")
    print("-" * 72)
    for line in run_bot_turn(state, "A", cards):
        print("  ", line)
    print(f"-> Vida Boltyn: {state.players['B'].life}; "
          f"auras/board Enigma: {state.players['A'].auras}")
    print()


def scenario_phantasm(cards):
    """C) Phantasm: o Valiant Thrust (red) carregado é um popper contra você."""
    print("=" * 72)
    print("C) PHANTASM — Enigma Chimera (6, Illusionist) vs Valiant Thrust (7)")
    print("=" * 72)

    state = make_state()
    a = state.players["A"]
    a.hand = ["Enigma Chimera (blue)"]
    a.pitch_pool = 2
    b = state.players["B"]
    b.hand = ["Valiant Thrust (red)"]
    combat.start_turn(state, "A")

    link = combat.declare_attack(state, "A", "Enigma Chimera (blue)", cards)
    print(f"Enigma ataca com Enigma Chimera ({link.total_damage}p).")
    combat.defend_link(state, "B", ["Valiant Thrust (red)"], cards)
    vt = cards["Valiant Thrust (red)"]
    chimera = cards["Enigma Chimera (blue)"]
    is_phantasm_pop = (
        "Phantasm" in chimera.keywords
        and "Non-Illusionist" not in " ".join(chimera.keywords)
        and all(t not in vt.types for t in ("Illusionist",))
        and (vt.power or 0) + 3 >= 6
    )
    pop = is_phantasm_pop
    print(f"Boltyn defende com Valiant Thrust (red) "
          f"(power {vt.power}+3 = 7, tipos {vt.types}).")
    if pop:
        print("=> PHANTASM dispara (CR 8.3.13): Enigma Chimera é DESTRUÍDA e o")
        print("   ataque não resolve. Regra: não exponha Phantasm ao Valiant carregado.")
    else:
        print("=> sem trigger.")
    print()

    state2 = make_state()
    state2.players["A"].hand = ["Spectral Manifestations (red)", "Astral Etchings (red)"]
    state2.players["A"].pitch_pool = 2
    combat.start_turn(state2, "A")
    for n in combat.play_aura_engine(state2, "A", "Spectral Manifestations (red)", cards):
        print("  ", n.text)
    state2.players["A"].pitch_pool += 1  # Astral Etchings cost
    for n in combat.astral_charge(state2, "A", cards):
        print("  ", n.text)
    aura_key = next(k for k in state2.players["A"].auras if "Spectral Shield" in k)
    c_link = combat.attack_with_aura(state2, "A", aura_key, cards)
    shield = cards[aura_key]
    print(f"Cosmo ataca com {aura_key} ({c_link.total_damage}p).")
    print(f"  -> Aura NÃO tem Phantasm: o Valiant Thrust não pode destruí-la. "
          f"Essa é a saída contra block grande.")


def main() -> None:
    cards = load_cards()
    scenario_boltyn_turn(cards)
    scenario_enigma_turn(cards)
    scenario_phantasm(cards)


if __name__ == "__main__":
    main()