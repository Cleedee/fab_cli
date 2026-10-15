#!/usr/bin/env python3
"""Simulação de matchup Enigma (Colin Li) vs Dromai usando o motor real do projeto.

Uso:
    python scripts/sim_enigma_vs_dromai.py

Roda três cenários, sem alterar nenhum dado do repo:

    A) Turno da Enigma com abertura de motor (plan_enigma + run_bot_turn).
    B) Onda de 3 dragões da Dromai e o que o suggest_defense escolhe bloquear.
    C) Matemática de matar um dragão num turno (vida de ala reseta no End Phase).

É apoio à decisão, não simulador de regras completo: o motor não modela as alas
da Dromai, então cada dragão é injetado como um ChainLink e resolvido à mão.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from flesh_and_blood import combat
from flesh_and_blood.bot import run_bot_turn
from flesh_and_blood.carddb import load_cards
from flesh_and_blood.defense import suggest_defense
from flesh_and_blood.heroes import plan_enigma
from flesh_and_blood.models import ChainLink, Hero, new_game

# Vida das alas (allies) da Dromai, do card.json (the-fab-cube). O modelo Card
# do repo não carrega o campo health, por isso fixamos aqui para o cenário C.
DRAGON_HEALTH = {
    "Azvolai": 3,
    "Cromai": 2,
    "Kyloria": 2,
    "Miragai": 4,
    "Themai": 4,
    "Ouvia": 6,
    "Yendurai": 3,
}

# Poder de cada dragão atacando (todos com Go Again) + dano arcano, se houver.
DROMAI_WAVE = [("Azvolai", 2, 1), ("Cromai", 3, 0), ("Kyloria", 4, 0)]

ENIGMA_EQUIPMENT = [
    "Blade Beckoner Helm",
    "Blade Beckoner Plating",
    "Uphold Tradition",
    "Silent Stilettos",
]
COSMO = "Cosmo, Scroll of Ancestral Tapestry"


def make_state():
    """Estado base: Enigma (A) vs Dromai (B), com equipamento e arma da Enigma."""
    enigma = Hero(
        key="Enigma",
        name="Enigma",
        life=20,
        intellect=4,
        classes=("Illusionist",),
        talents=("Mystic",),
    )
    dromai = Hero(
        key="Dromai",
        name="Dromai",
        life=20,
        intellect=4,
        classes=("Illusionist",),
        talents=("Draconic",),
    )
    state = new_game(enigma, dromai, first_player="A")
    combat.start_turn(state, "A")
    a = state.players["A"]
    a.weapons = [COSMO]
    a.equipment_uses = list(ENIGMA_EQUIPMENT)
    return state


def scenario_enigma_turn(cards):
    """A) Turno da Enigma com abertura de motor."""
    state = make_state()
    state.players["A"].hand = [
        "Spectral Manifestations (red)",
        "Astral Etchings (red)",
        "Solitary Companion (red)",
        "Clear Conscience (red)",
        "Enigma Chimera (blue)",
    ]
    plan = plan_enigma(state, "A", cards)
    print("=" * 70)
    print("A) TURNO DA ENIGMA — abertura de motor")
    print("=" * 70)
    print("Mão:", ", ".join(state.players["A"].hand))
    print("Plano:", plan.steps)
    print(f"Dano físico estimado: {plan.physical} | pitched: {plan.pitched}")
    print("-" * 70)
    for line in run_bot_turn(state, "A", cards):
        print("  ", line)
    print(
        f"-> Vida Dromai: {state.players['B'].life}; auras/board Enigma: {state.players['A'].auras}"
    )
    print()


def scenario_dromai_wave(cards):
    """B) Onda de 3 dragões e a defesa escolhida pelo suggest_defense."""
    print("=" * 70)
    print("B) ONDA DA DROMAI (3 dragões) — defesa do Enigma")
    print("=" * 70)
    state = make_state()
    a = state.players["A"]
    a.hand = [
        "Clear Conscience (red)",
        "Springboard Somersault (yellow)",
        "Enigma Chimera (blue)",
        "Big Blue Sky (blue)",
        "On the Horizon (yellow)",
    ]
    combat.start_turn(state, "B")
    print("Mão da Enigma:", ", ".join(a.hand))
    print()

    hand = {k: cards[k] for k in a.hand if k in cards}
    for name, power, arcane in DROMAI_WAVE:
        equip = {
            k: (cards[k].defense or 0)
            for k in a.equipment_uses
            if k not in a.equipment_destroyed
            and k not in a.equipment_used_this_turn
            and cards[k].is_equipment
            and (cards[k].defense or 0) > 0
        }
        options = suggest_defense(power, hand, equip, top=3)
        print(f"{name} ({power}p + {arcane} arcano) — opções:")
        for opt in options:
            print(
                f"    defesa {opt.block_total}: cartas={list(opt.hand_cards)}, "
                f"equip={list(opt.equipment)}"
            )
        best = options[0]
        link = ChainLink(attacker="B", card_key=name, total_damage=power, arcane_damage=arcane)
        state.chain.append(link)
        for k in best.hand_cards:
            combat.defend_link(state, "A", [k], cards)
            hand.pop(k, None)
        for eq in best.equipment:
            combat.use_equipment_defense(state, "A", eq, cards)
        result = combat.resolve_link(state, cards, arcane_prevented=arcane)
        print(
            f"    => jogou {list(best.hand_cards) or 'só equipamento'}; "
            f"físico {result['physical']} / arcano {result['arcane']} "
            f"| vida Enigma: {state.players['A'].life}"
        )
        print()

    print("Observação: bloquear os 3 dragões custa a mão + peças de armadura; o")
    print("suggest_defense pode inclusive queimar peças de MOTOR (Spectral")
    print("Manifestations/Solitary Companion) por valor defensivo. Avalie deixar")
    print("dragões pequenos passarem para preservar a mão do motor.")
    print()


def scenario_kill_ally(cards):
    """C) Matemática de matar um dragão num único turno."""
    print("=" * 70)
    print("C) FOCO EM ALA — matar um dragão num único turno")
    print("=" * 70)
    for name, life in DRAGON_HEALTH.items():
        print(f"  {name:9} vida {life}")
    print()
    print("Spectral Shield (Ward 1 + 3 contadores de Spectral Manifestations) via")
    print("Cosmo = 4 de dano; com Astral Etchings (+3) = 7 -> mata qualquer dragão.")
    print("A ala NÃO pode ser defendida e sua vida reseta no End Phase:")
    print("logo é preciso matá-la de uma vez, não fatiar.")
    print()
    print("Clear Conscience (red, 8) é Illusionist => NÃO popa Phantasm (CR 8.3.13")
    print("exige attack action não-Illusionist 6+). Matar dragão = atacar a ala.")


def main() -> None:
    cards = load_cards()
    scenario_enigma_turn(cards)
    scenario_dromai_wave(cards)
    scenario_kill_ally(cards)


if __name__ == "__main__":
    main()
