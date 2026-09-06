"""Planejador de turno ofensivo: linha que maximiza dano com premissas explícitas.

Estratégia em três fases:
1. Monta a sequência pretendida (buffs -> maior ataque -> demais ataques -> arma),
   respeitando apenas AP/Go Again.
2. Viabiliza recursos: enquanto custos > pitch_pool + pitches das cartas que ficam
   na mão, corta do plano o ataque jogado de menor poder (vira pitch).
3. Reavalia dano físico/arcano/AP da sequência final, de forma determinística.

Multi-plan: tenta cada ataque como primeiro (excluindo buffs) e escolhe a
sequência com maior dano total. O plano é ESTIMATIVA para apoio a decisão,
não simulador de regras completo.
"""

from dataclasses import dataclass, field

from flesh_and_blood.models import Card, GameState

# Bônus de poder concedido por non-attack actions do pool atual.
BUFF_POWER = {
    "Sizzle": 3,
    "Weave Lightning": 3,
    "Nimblism": 3,
    "Sprout Strength": 3,  # três +1{p}; no somatório o total é o mesmo
}

# Dano arcano quando o ataque é jogado/atinge (assumimos que acerta).
ARCANE_ON_ATTACK = {
    "Arcanic Shockwave": 1,
    "Path of Same Ends": 1,
    "Stinging Sprite": 1,
    "Rush of Power": 1,
}

LOOK_TUFF = "Look Tuff"
LOOK_TUFF_EXTRA_COST = 1
SHOCKWAVE = "Arcanic Shockwave"
WEAPON_LIGHTNING_BONUS = 1

ASSUMPTIONS = [
    "Todos os ataques acertam (sem bloqueio do oponente).",
    "Rush of Power só tem o +1{p} com Go Again externo (não assumido aqui).",
    "Cartas não podem pagar o próprio custo com o próprio pitch.",
]


@dataclass
class AttackPlan:
    """Resultado do planejamento de burst/lethal."""

    sequence: list[str] = field(default_factory=list)
    pitched: list[str] = field(default_factory=list)
    physical: int = 0
    arcane: int = 0
    resources_left: int = 0
    action_points_left: int = 0
    lethal: bool = False
    arsenal_suggestion: str | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.physical + self.arcane


# Cartas do motor Enigma (Cosmo/auras/transcend).
SPECTRAL_MANIFESTATIONS = "Spectral Manifestations"
SOLITARY_COMPANION = "Solitary Companion"
WAXING_SPECTER = "Waxing Specter"
WANING_VENGEANCE = "Waning Vengeance"
ASTRAL_ETCHINGS = "Astral Etchings"
TRANSCEND_CARDS = {"Homage to Ancestors", "Pass Over", "Preserve Tradition"}
SECOND_TENET = "Second Tenet of Chi"
SPECTRAL_SHIELD = "Spectral Shield"


@dataclass
class EnigmaPlan:
    """Linha de jogo que maximiza dano usando o motor de auras do Cosmo.

    steps são tuplas (ação, parâmetro) para o bot executar:
    - ("pitch", key)            picha carta da mão
    - ("activate_enigma",)      ativa a habilidade uma vez por turno
    - ("play", key)             joga carta (action ou instant-aura)
    - ("cosmo", aura_key)       ataque de aura via Cosmo
    - ("attack", key)           ataque da mão/arsenal
    - ("resolve",)              resolve o último link
    """

    steps: list[tuple] = field(default_factory=list)
    pitched: list[str] = field(default_factory=list)
    physical: int = 0
    lethal: bool = False
    notes: list[str] = field(default_factory=list)


ENIGMA_ASSUMPTIONS = [
    "Todos os ataques acertam (sem bloqueio do oponente).",
    "Ataques de aura do Cosmo não destroem a aura (fica em jogo até resolver).",
    "Transcend e condicionais de contadores são estimados com as premissas da mão.",
    "Fluid Motion/Spears considerados com Go Again (dataset não modela as condições).",
]


def _ward_base(card: Card) -> int:
    for kw in card.keywords:
        if kw.startswith("Ward") and kw.replace("Ward", "").strip().isdigit():
            return int(kw.replace("Ward", "").strip())
    return 0


def _is_buff(card: Card) -> bool:
    return card.is_non_attack_action and (card.name in BUFF_POWER or "Go again" in card.keywords)


def _power(card: Card, pay_extra: bool) -> int:
    base = card.power or 0
    if card.name == LOOK_TUFF and not pay_extra:
        return base - 1
    return base


def _ping(card: Card, fused_ok: bool) -> int:
    ping = ARCANE_ON_ATTACK.get(card.name, 0)
    if card.name == SHOCKWAVE and not fused_ok:
        return 0
    return ping


def _arsenal_score(card: Card) -> float:
    """Pontuação de uma carta para arsenal: defesa + pitch valorizam o próximo turno."""
    defense = card.defense or 0
    pitch = card.pitch or 0
    power = card.power or 0
    return defense + pitch + power * 0.5


def _ap_left(player, hand: dict[str, Card], sequence: list[str]) -> int:
    """AP restante após executar a sequência (Go Again e aura considerados)."""
    ap = player.action_points
    aura = "Embodiment of Lightning" in player.auras
    for k in sequence:
        card = hand[k]
        if _is_buff(card):
            ap -= 1
            if "Go again" in card.keywords:
                ap += 1
            continue
        innate_ga = "Go again" in card.keywords
        used_aura = False
        if not innate_ga and aura:
            aura = False
            used_aura = True
        ap -= 1
        if innate_ga or used_aura:
            ap += 1
    return ap


def _build_plan_from_order(
    me,
    hand: dict[str, Card],
    cards: dict[str, Card],
    weapon_key: str | None,
    life: int,
    intended: list[str],
    original_notes: list[str],
) -> AttackPlan:
    """Constrói um plano completo a partir de uma sequência pretendida.

    Executa as 3 fases (sequência, viabilidade, avaliação) + arma + pitch +
    arsenal, retornando o AttackPlan avaliado.
    """
    plan = AttackPlan()
    plan.notes.extend(original_notes)

    ap = me.action_points
    aura_ga = "Embodiment of Lightning" in me.auras
    sequence: list[str] = []
    played_set: set[str] = set()
    costs: dict[str, int] = {}
    pay_extra_for: set[str] = set()

    # ---- Fase 1: monta sequência pretendida --------------------------------
    for key in intended:
        card = hand[key]
        if ap < 1:
            plan.notes.append(f"{card.name}: sem AP.")
            continue
        innate_ga = "Go again" in card.keywords
        used_aura = False
        if not innate_ga and aura_ga:
            aura_ga = False
            used_aura = True
        ap -= 1
        if innate_ga or used_aura:
            ap += 1
        sequence.append(key)
        played_set.add(key)
        cost = card.cost or 0
        if card.name == LOOK_TUFF:
            potential = me.pitch_pool + sum(hand[k].pitch or 0 for k in hand if k not in played_set)
            if potential >= sum(costs.values()) + cost + LOOK_TUFF_EXTRA_COST:
                pay_extra_for.add(key)
                cost += LOOK_TUFF_EXTRA_COST
        costs[key] = cost

    # ---- Fase 2: viabilidade de recursos -----------------------------------
    def available_now() -> int:
        return me.pitch_pool + sum(hand[k].pitch or 0 for k in hand if k not in played_set)

    while sum(costs.values()) > available_now():
        downgraded = False
        for k in list(pay_extra_for):
            if k in sequence and k in hand and hand[k].name == LOOK_TUFF:
                costs[k] -= LOOK_TUFF_EXTRA_COST
                pay_extra_for.discard(k)
                plan.notes.append(
                    f"{hand[k].name}: sem {LOOK_TUFF_EXTRA_COST}{{r}} extra -> "
                    f"{_power(hand[k], False)}{{p}}."
                )
                downgraded = True
                break
        if downgraded:
            continue
        victims = [k for k in sequence if k in hand]
        if not victims:
            break
        victim = min(victims, key=lambda k: hand[k].power or 0)
        sequence.remove(victim)
        played_set.discard(victim)
        del costs[victim]
        pay_extra_for.discard(victim)
        plan.notes.append(f"{hand[victim].name}: cortado do plano para virar pitch.")

    # ---- Arma: avaliada com AP e recursos FINAIS da sequência ---------------
    weapon_in_plan = False
    if weapon_key is None:
        plan.notes.append("Sem arma informada: plano considera só cartas.")
    elif me.weapon_attacks_this_turn:
        plan.notes.append("Arma já usada neste turno.")
    elif _ap_left(me, hand, sequence) < 1:
        plan.notes.append(f"{cards[weapon_key].name}: sem AP para atacar com a arma.")
    elif sum(costs.values()) + 1 > available_now():
        plan.notes.append(f"{cards[weapon_key].name}: sem recursos para o {{r}}.")
    else:
        sequence.append(weapon_key)
        weapon_in_plan = True
        costs[weapon_key] = 1

    # ---- Fase 3: avaliação determinística -----------------------------------
    phys = 0
    arc = 0
    ap = me.action_points
    aura_ga = "Embodiment of Lightning" in me.auras
    lightning_played = False

    for key in sequence:
        if key == weapon_key and weapon_in_plan:
            power = (cards[weapon_key].power or 0) + (
                WEAPON_LIGHTNING_BONUS if lightning_played else 0
            )
            phys += power
            ap -= 1
            if lightning_played:
                ap += 1
                plan.notes.append(f"{cards[weapon_key].name}: +1{{p}} e Go Again por Lightning.")
            continue
        card = hand[key]
        if _is_buff(card):
            ap -= 1
            if "Go again" in card.keywords:
                ap += 1
            phys += BUFF_POWER.get(card.name, 0)
        else:
            innate_ga = "Go again" in card.keywords
            used_aura = False
            if not innate_ga and aura_ga:
                aura_ga = False
                used_aura = True
                plan.notes.append(f"{card.name}: consome Embodiment of Lightning -> Go Again.")
            ap -= 1
            if innate_ga or used_aura:
                ap += 1
            fused_ok = lightning_played or any(
                "Lightning" in hand[k].types for k in sequence[: sequence.index(key)] if k in hand
            )
            phys += _power(card, key in pay_extra_for)
            if card.name == LOOK_TUFF and key not in pay_extra_for:
                plan.notes.append(
                    f"{card.name}: sem {LOOK_TUFF_EXTRA_COST}{{r}} extra -> "
                    f"{_power(card, False)}{{p}}."
                )
            arc += _ping(card, fused_ok)
            if card.name == SHOCKWAVE and not fused_ok:
                plan.notes.append("Shockwave SEM fusão: sem arcano.")
            elif card.name == SHOCKWAVE:
                plan.notes.append("Shockwave fundida (+1 arcano).")
        if "Lightning" in card.types:
            lightning_played = True

    # Pitch necessário além do pool atual: menor pitch primeiro (preserva azuis).
    pending = max(0, sum(costs.values()) - me.pitch_pool)
    for k in sorted((k for k in hand if k not in played_set), key=lambda k: hand[k].pitch or 0):
        if pending <= 0:
            break
        if (hand[k].pitch or 0) > 0:
            plan.pitched.append(k)
            pending -= hand[k].pitch or 0

    plan.sequence = sequence
    plan.physical = phys
    plan.arcane = arc
    plan.resources_left = max(0, me.pitch_pool - sum(costs.values()))
    plan.action_points_left = ap
    plan.lethal = plan.total >= life

    # Arsenal: se sobrou AP e há cartas na mão que não foram jogadas,
    # sugere arsenalar a de maior valor defensivo+recurso para o próximo turno.
    unplayed = [k for k in hand if k not in played_set and k not in plan.pitched]
    if ap >= 1 and me.arsenal is None and unplayed:
        best = max(unplayed, key=lambda k: _arsenal_score(hand[k]))
        plan.arsenal_suggestion = best
        plan.notes.append(
            f"Arsenal sugerido: {hand[best].name} "
            f"(def {hand[best].defense or 0}, pitch {hand[best].pitch or 0})."
        )

    return plan


def plan_attack(
    state: GameState,
    side: str,
    cards: dict[str, Card],
    *,
    opponent_life: int | None = None,
    weapon_key: str | None = None,
) -> AttackPlan:
    """Monta a linha de jogo que maximiza dano físico+arcano do turno.

    Considera mão + arsenal, recursos (pitch_pool + pitches possíveis),
    action points, Go Again inato, Embodiment of Lightning e a arma
    once-per-turn (`weapon_key` vem da decklist do jogador).

    Multi-plan: gera variantes com cada ataque como primeiro (excluindo
    buffs) e escolhe a de maior dano total.
    """
    me = state.players[side]
    other_side = next(s for s in state.players if s != side)
    life = opponent_life if opponent_life is not None else state.players[other_side].life

    hand: dict[str, Card] = {}
    for key in [*me.hand, *([me.arsenal] if me.arsenal else [])]:
        if key not in cards:
            raise ValueError(f"carta ausente do registro: {key}")
        hand[key] = cards[key]

    attacks = [k for k, c in hand.items() if c.is_attack]
    buffs = [k for k, c in hand.items() if _is_buff(c)]

    # Gera candidatos: cada ataque não-buff como primeiro, mantendo
    # a ordem original dos demais.
    candidates: list[list[str]] = []
    for i, first in enumerate(attacks):
        order = buffs + [first] + [a for j, a in enumerate(attacks) if j != i]
        candidates.append(order)

    # Fallback: sem ataques — usa só buffs + arma.
    if not candidates:
        candidates.append(buffs)

    best: AttackPlan | None = None
    for order in candidates:
        candidate = _build_plan_from_order(me, hand, cards, weapon_key, life, order, ASSUMPTIONS)
        if best is None or candidate.total > best.total:
            best = candidate

    return best


def plan_enigma(
    state: GameState,
    side: str,
    cards: dict[str, Card],
    *,
    opponent_life: int | None = None,
) -> EnigmaPlan:
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

    plan = EnigmaPlan()
    plan.notes.extend(ENIGMA_ASSUMPTIONS)

    pool = me.pitch_pool
    ap = me.action_points
    unplayed = set(hand)  # cartas ainda candidatas a ataque
    played_set: set[str] = set()
    # auras simuladas deste turno: chave -> contadores da cópia "melhor"
    aura_counts: dict[str, int] = {
        k: max(v) for k, v in me.auras.items() if _ward_base(cards.get(k)) > 0
    }
    created_cards = 0
    transcended = False
    shield_created = False

    def pitchable_count(exclude: str | None = None) -> int:
        return sum((hand[k].pitch or 0) for k in unplayed if k != exclude)

    def affordable(cost: int, exclude: str | None = None) -> bool:
        return pool >= cost or pool + pitchable_count(exclude) >= cost

    def pay(cost: int) -> bool:
        nonlocal pool
        while pool < cost:
            if not unplayed:
                return False
            # picha a de menor pitch primeiro (preserva azuis para custos maiores)
            k = min(unplayed, key=lambda k: (hand[k].pitch or 0, hand[k].name))
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
        key=lambda kv: max(_ward_base(cards.get(kv[0]) or cards[kv[0]]), 0) + kv[1],
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
        plan.physical += max(_ward_base(cards.get(aura_key) or cards[aura_key]), 0) + counters
        ap -= 1
        if counters > 0:
            ap += 1
    del spectral_attack_estimate

    # --- 5. Ataques de mão: Go Again primeiro, depois maior poder -------------
    def attack_value(key: str) -> tuple:
        c = hand[key]
        ga = "Go again" in c.keywords
        transc_bonus = 2 if transcended and key.startswith(SECOND_TENET) else 0
        return (ga, (c.power or 0) + transc_bonus)

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
        transc_bonus = 2 if transcended and key.startswith(SECOND_TENET) else 0
        plan.physical += (card.power or 0) + transc_bonus

    plan.steps.append(("resolve",))
    plan.lethal = plan.physical >= life
    return plan
