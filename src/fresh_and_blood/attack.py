"""Planejador de turno ofensivo: linha que maximiza dano com premissas explícitas.

Estratégia em três fases:
1. Monta a sequência pretendida (buffs -> maior ataque -> demais ataques -> arma),
   respeitando apenas AP/Go Again.
2. Viabiliza recursos: enquanto custos > pitch_pool + pitches das cartas que ficam
   na mão, corta do plano o ataque jogado de menor poder (vira pitch).
3. Reavalia dano físico/arcano/AP da sequência final, de forma determinística.

O plano é ESTIMATIVA para apoio a decisão, não simulador de regras completo.
"""

from dataclasses import dataclass, field

from fresh_and_blood.models import Card, GameState

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
    notes: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.physical + self.arcane


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
    """
    me = state.players[side]
    other_side = next(s for s in state.players if s != side)
    life = opponent_life if opponent_life is not None else state.players[other_side].life

    plan = AttackPlan()
    plan.notes.extend(ASSUMPTIONS)

    hand: dict[str, Card] = {}
    for key in [*me.hand, *([me.arsenal] if me.arsenal else [])]:
        if key not in cards:
            raise ValueError(f"carta ausente do registro: {key}")
        hand[key] = cards[key]

    # ---- Fase 1: sequência pretendida -------------------------------------
    attacks = [k for k, c in hand.items() if c.is_attack]
    buffs = [k for k, c in hand.items() if _is_buff(c)]
    big_non_ga = max(
        (k for k in attacks if "Go again" not in hand[k].keywords),
        key=lambda k: hand[k].power or 0,
        default=None,
    )
    rest = [k for k in attacks if k != big_non_ga]
    rest.sort(key=lambda k: ("Go again" not in hand[k].keywords, -(hand[k].power or 0)))
    intended = buffs + ([big_non_ga] if big_non_ga else []) + rest

    ap = me.action_points
    aura_ga = "Embodiment of Lightning" in me.auras
    sequence: list[str] = []
    played: set[str] = set()
    costs: dict[str, int] = {}
    pay_extra_for: set[str] = set()

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
        played.add(key)
        cost = card.cost or 0
        # Decide já sobre o {r} extra do Look Tuff (revisado na fase 2 se faltar recurso).
        if card.name == LOOK_TUFF:
            potential = me.pitch_pool + sum(hand[k].pitch or 0 for k in hand if k not in played)
            if potential >= sum(costs.values()) + cost + LOOK_TUFF_EXTRA_COST:
                pay_extra_for.add(key)
                cost += LOOK_TUFF_EXTRA_COST
        costs[key] = cost

    # A arma é avaliada DEPOIS da fase 2: cartas cortadas por falta de recurso
    # liberam AP que a arma pode usar.

    # ---- Fase 2: viabilidade de recursos ----------------------------------
    def available_now() -> int:
        return me.pitch_pool + sum(hand[k].pitch or 0 for k in hand if k not in played)

    while sum(costs.values()) > available_now():
        # Tenta primeiro downgrade do Look Tuff (joga sem o {r} extra).
        downgraded = False
        for k in list(pay_extra_for):
            if k in sequence and k in hand and hand[k].name == LOOK_TUFF:
                costs[k] -= LOOK_TUFF_EXTRA_COST
                pay_extra_for.discard(k)
                plan.notes.append(
                    f"{hand[k].name}: sem {LOOK_TUFF_EXTRA_COST}{{r}} extra -> {_power(hand[k], False)}{{p}}."
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
        played.discard(victim)
        del costs[victim]
        pay_extra_for.discard(victim)
        plan.notes.append(f"{hand[victim].name}: cortado do plano para virar pitch.")

    # ---- Arma: avaliada com o AP e recursos FINAIS da sequência -------------
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

    # ---- Fase 3: avaliação determinística ---------------------------------
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
                ap += 1  # Go Again condicional do Star Fall
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
                    f"{card.name}: sem {LOOK_TUFF_EXTRA_COST}{{r}} extra -> {_power(card, False)}{{p}}."
                )
            arc += _ping(card, fused_ok)
            if card.name == SHOCKWAVE and not fused_ok:
                plan.notes.append("Shockwave SEM fusão: sem arcano.")
            elif card.name == SHOCKWAVE:
                plan.notes.append("Shockwave fundida (+1 arcano).")
        if "Lightning" in card.types:
            lightning_played = True

    # Pitch necessário além do pool atual: maiores pitches primeiro.
    pending = max(0, sum(costs.values()) - me.pitch_pool)
    for k in sorted((k for k in hand if k not in played), key=lambda k: -(hand[k].pitch or 0)):
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
    return plan
