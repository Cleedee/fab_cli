"""Estratégia do Enigma (Mystic Illusionist): motor Cosmo/auras.

Concentra todo o conhecimento do herói Enigma que antes ficava misturado em
``attack.py`` e ``defense.py``:

- ``plan_enigma`` — linha de turno (motor de auras + Cosmo + ataques);
- ``EnigmaStrategy.hand_value_bonus`` — peças de motor valem mais na defesa;
- notas de matchup (evita Phantasm contra block grande; lê a ameaça do oponente).
"""

from __future__ import annotations

from flesh_and_blood.heroes.base import HeroStrategy, TurnPlan, ward_base
from flesh_and_blood.heroes.matchups import phantasm_risk, threat_report
from flesh_and_blood.models import Card, GameState

# Cartas do motor Enigma (Cosmo/auras/transcend).
SPECTRAL_MANIFESTATIONS = "Spectral Manifestations"
SOLITARY_COMPANION = "Solitary Companion"
WAXING_SPECTER = "Waxing Specter"
WANING_VENGEANCE = "Waning Vengeance"
ASTRAL_ETCHINGS = "Astral Etchings"
TRANSCEND_CARDS = {"Homage to Ancestors", "Pass Over", "Preserve Tradition"}
SECOND_TENET = "Second Tenet of Chi"
SPECTRAL_SHIELD = "Spectral Shield"
UNFLINCHING_FOOTHOLD = "Unflinching Foothold"

ENIGMA_ASSUMPTIONS = [
    "Todos os ataques acertam (sem bloqueio do oponente).",
    "Ataques de aura do Cosmo não destroem a aura (fica em jogo até resolver).",
    "Transcend e condicionais de contadores são estimados com as premissas da mão.",
    "Fluid Motion/Spears considerados com Go Again (dataset não modela as condições).",
]


def plan_enigma(
    state: GameState,
    side: str,
    cards: dict[str, Card],
    *,
    opponent_life: int | None = None,
) -> TurnPlan:
    """Monta a linha de jogo do Enigma (motor de auras + Cosmo + ataques).

    Estratégia (greedy determinística):
    1. Ativa o Enigma se houver recursos (cria Spectral Shield +1 contador).
    2. Joga o motor de auras: Spectral Manifestations, Solitary Companion,
       Waxing/Waning Vengeance e astral charges.
    3. Transcend (Homage/Pass Over/Preserve) se um Second Tenet estiver na mão.
    4. Ataca com cada aura via Cosmo (1º Spectral Shield custa 0), depois
       os ataques de mão (Go Again primeiro) e resolve.

    É ESTIMATIVA para apoio à decisão, não simulador de regras completo.
    """
    me = state.players[side]
    if me.hero_key != "Enigma":
        raise ValueError("plan_enigma é específico do herói Enigma")
    other_side = next(s for s in state.players if s != side)
    life = opponent_life if opponent_life is not None else state.players[other_side].life

    hand: dict[str, Card] = {}
    for key in [*me.hand, *([me.arsenal] if me.arsenal else [])]:
        if key not in cards:
            raise ValueError(f"carta ausente do registro: {key}")
        hand[key] = cards[key]

    # Leitura de mesa: risco de Phantasm (block grande) e ameaça do oponente.
    opponent = state.players[other_side]
    phantasm_popper = phantasm_risk(opponent, cards)
    risky = phantasm_popper is not None

    plan = TurnPlan()
    plan.notes.extend(ENIGMA_ASSUMPTIONS)
    plan.notes.extend(threat_report(state, side, cards))

    pool = me.pitch_pool
    ap = me.action_points
    unplayed = set(hand)  # cartas ainda candidatas a ataque
    played_set: set[str] = set()
    # auras simuladas deste turno: chave -> contadores da cópia "melhor"
    aura_counts: dict[str, int] = {
        k: max(v) for k, v in me.auras.items() if ward_base(cards.get(k)) > 0
    }
    created_cards = 0
    transcended = False
    shield_created = False

    def pitchable_count(exclude: str | None = None) -> int:
        return sum((hand[k].pitch or 0) for k in unplayed if k != exclude)

    def affordable(cost: int, exclude: str | None = None) -> bool:
        return pool >= cost or pool + pitchable_count(exclude) >= cost

    def _pitch_preference(k: str) -> tuple:
        c = hand[k]
        is_def = ("Block" in c.types) or ("Defense Reaction" in c.types)
        is_engine = c.name == SPECTRAL_MANIFESTATIONS or c.name == SOLITARY_COMPANION
        is_charge = c.name == ASTRAL_ETCHINGS
        is_attack = c.is_attack
        # Pitch order: defense first (0), others middle (1), attacks middle-high (2),
        # engine/charge LAST (3) to preserve them
        if is_engine or is_charge:
            pref = 3
        elif is_attack:
            pref = 2
        elif is_def:
            pref = 0
        else:
            pref = 1
        return (pref, c.pitch or 0, c.name)

    def pay(cost: int) -> bool:
        nonlocal pool
        while pool < cost:
            if not unplayed:
                return False
            k = min(unplayed, key=_pitch_preference)
            if (hand[k].pitch or 0) <= 0:
                return False
            if k not in plan.pitched:
                plan.pitched.append(k)
                plan.steps.append(("pitch", k))
            played_set.add(k)
            unplayed.discard(k)
            pool += hand[k].pitch or 0
        pool -= cost
        return True

    def want_play(key: str, cost: int) -> bool:
        if key != "__enigma__" and key not in hand:
            return False
        return key not in played_set and affordable(
            cost, exclude=None if key == "__enigma__" else key
        )

    # --- 1. Motor: Spectral Manifestations cria o shield grande -------------
    mani = f"{SPECTRAL_MANIFESTATIONS} (red)"
    if want_play(mani, 2):
        played_set.add(mani)
        unplayed.discard(mani)
        if pay(2):
            plan.steps.append(("play", mani))
            created_cards += 1
            aura_counts[SPECTRAL_SHIELD] = 3  # sem outras auras Illusionist
            shield_created = True
        else:
            played_set.discard(mani)
            unplayed.add(mani)
    else:
        solo = f"{SOLITARY_COMPANION} (red)"
        if want_play(solo, 0):
            played_set.add(solo)
            unplayed.discard(solo)
            if pay(0):
                plan.steps.append(("play", solo))
                created_cards += 1
                aura_counts[solo] = 0
                if not shield_created:
                    aura_counts[SPECTRAL_SHIELD] = 1
                    shield_created = True
            else:
                played_set.discard(solo)
                unplayed.add(solo)

    # --- 1b. Enigma: ativa se sobra recurso pós-motor ---
    if not me.hero_ability_used and want_play("__enigma__", 3):
        played_set.add("__enigma__")
        if pay(3):
            plan.steps.append(("activate_enigma",))
            # cria uma CÓPIA nova de Spectral Shield (+1 contador): a melhor
            # cópia existente (max) não muda; se não havia shield, nasce com 1.
            aura_counts[SPECTRAL_SHIELD] = max(aura_counts.get(SPECTRAL_SHIELD, 0), 1)
            shield_created = True
            created_cards += 1
        else:
            played_set.discard("__enigma__")

    # --- 1c. Instants de aura (Waxing/Waning) — sem custo de AP ---
    for key, cost in ((f"{WAXING_SPECTER} (red)", 2), (f"{WANING_VENGEANCE} (red)", 1)):
        if want_play(key, cost):
            played_set.add(key)
            unplayed.discard(key)
            if pay(cost):
                plan.steps.append(("play", key))
                counters = 1 if key.startswith(WAXING_SPECTER) else 0  # +1 se pitchou blue
                aura_counts[key] = counters
                created_cards += 1
            else:
                played_set.discard(key)
                unplayed.add(key)

    # --- 2. Charge: Astral Etchings +3 contadores na melhor aura ---
    etch = f"{ASTRAL_ETCHINGS} (red)"
    if want_play(etch, 1) and aura_counts:
        played_set.add(etch)
        unplayed.discard(etch)
        if pay(1):
            plan.steps.append(("play", etch))
            best = max(aura_counts, key=lambda k: aura_counts[k])
            aura_counts[best] += 3
            created_cards += 1
        else:
            played_set.discard(etch)
            unplayed.add(etch)

    # --- 3. Transcend engine (0 custo; marca o bônus dos Second Tenet) -------
    for key in [f"{t} (blue)" for t in TRANSCEND_CARDS]:
        if want_play(key, 0):
            played_set.add(key)
            unplayed.discard(key)
            if pay(0):
                plan.steps.append(("play", key))
                transcended = True
            else:
                played_set.discard(key)
                unplayed.add(key)
            break

    # --- 4. Ataques de aura (Cosmo): maior ward primeiro (fluxo de Go Again) --
    spectral_attack_estimate = me.spectral_attacks_this_turn
    for aura_key, counters in sorted(
        aura_counts.items(),
        key=lambda kv: ward_base(cards.get(kv[0])) + kv[1],
        reverse=True,
    ):
        if aura_key in me.weapon_attacks_this_turn:
            continue
        cost = 0 if aura_key == SPECTRAL_SHIELD else 1
        if aura_key == SPECTRAL_SHIELD and spectral_attack_estimate == 0:
            cost = 0
        if ap < 1 or not affordable(cost):
            break
        if not pay(cost):
            break
        if aura_key == SPECTRAL_SHIELD:
            spectral_attack_estimate += 1
        plan.steps.append(("cosmo", aura_key))
        plan.physical += ward_base(cards.get(aura_key)) + counters
        ap -= 1
        if counters > 0:
            ap += 1
    del spectral_attack_estimate

    # --- 5. Ataques de mão: Go Again primeiro, depois maior poder -------------
    #     Sob risco de Phantasm, prioriza ataques que NÃO podem ser destruídos.
    def attack_value(key: str) -> tuple:
        c = hand[key]
        ga = "Go again" in c.keywords
        transc_bonus = 2 if transcended and key.startswith(SECOND_TENET) else 0
        phantasm_safe = 0 if (risky and "Phantasm" in c.keywords) else 1
        return (phantasm_safe, ga, (c.power or 0) + transc_bonus)

    attacks = [k for k in hand if hand[k].is_attack and k not in played_set]
    for key in sorted(attacks, key=attack_value, reverse=True):
        card = hand[key]
        cost = card.cost or 0
        if ap < 1 or not affordable(cost, exclude=key):
            continue
        played_set.add(key)
        unplayed.discard(key)
        if not pay(cost):
            plan.notes.append(f"{card.name}: sem recursos para jogar.")
            played_set.discard(key)
            unplayed.add(key)
            continue
        ap -= 1
        if "Go again" in card.keywords:
            ap += 1
        plan.steps.append(("attack", key))
        plan.sequence.append(card.name)
        transc_bonus = 2 if transcended and key.startswith(SECOND_TENET) else 0
        plan.physical += (card.power or 0) + transc_bonus

    plan.steps.append(("resolve",))
    plan.lethal = plan.physical >= life
    return plan


class EnigmaStrategy(HeroStrategy):
    """Estratégia do Enigma baseada no motor Cosmo/auras."""

    hero_key = "Enigma"
    label = "Enigma (Cosmo/auras)"

    def plan_turn(
        self,
        state: GameState,
        side: str,
        cards: dict[str, Card],
        *,
        opponent_life: int | None = None,
    ) -> TurnPlan:
        return plan_enigma(state, side, cards, opponent_life=opponent_life)

    def hand_value_bonus(self, card: Card) -> float:
        # Peças de motor/charge não devem virar bloco nem pitch facilmente.
        if card.name in (SPECTRAL_MANIFESTATIONS, SOLITARY_COMPANION):
            return 6.0
        if card.name == ASTRAL_ETCHINGS:
            return 5.0
        # Anti-Dominate: guardar para o turno de crush do Bravo.
        if card.name == UNFLINCHING_FOOTHOLD:
            return 5.0
        return 0.0
