"""Sugeridor de defesa: minimiza dano sofrido preservando valor de mão.

Estratégia: enumerar subsets da mão (viável até ~10 cartas) e dos
equipamentos disponíveis, respeitando Dominate quando ativo, e ordenar as
opções por (dano sofrido, valor perdido, nº de cartas). O valor de mão é
uma heurística configurável — não é verdade de mesa.
"""

from dataclasses import dataclass
from itertools import combinations

from fresh_and_blood.models import Card

MAX_ENUM_CARDS = 10
EQUIPMENT_USE_COST = 0.25


@dataclass(frozen=True)
class ValueWeights:
    """Pesos do custo de oportunidade de bloquear com cada carta."""

    base: float = 1.0
    attack_bonus: float = 1.5
    go_again_bonus: float = 0.75
    cost_threshold: int = 3
    expensive_bonus: float = 1.0
    dr_bonus: float = 0.25


DEFAULT_WEIGHTS = ValueWeights()


def card_value(card: Card, w: ValueWeights = DEFAULT_WEIGHTS) -> float:
    """Valor heurístico de manter a carta na mão (quanto maior, menos queremos gastar)."""
    value = w.base
    if card.is_attack:
        value += w.attack_bonus
    if "Go again" in card.keywords:
        value += w.go_again_bonus
    if (card.cost or 0) >= w.cost_threshold:
        value += w.expensive_bonus
    if "Defense Reaction" in card.types:
        value += w.dr_bonus
    return value


@dataclass(frozen=True)
class DefenseOption:
    """Uma linha de defesa candidata."""

    hand_cards: tuple[str, ...]
    equipment: tuple[str, ...]
    block_total: int
    damage_taken: int
    value_lost: float


def _dominate_ok(cards_and_eq: list[tuple[str, bool]]) -> bool:
    """Dominate: no máximo 2 cartas, sendo no máximo 1 action card.

    `cards_and_eq` traz pares (chave, é_action_card); equipamentos entram
    como não-action.
    """
    if len(cards_and_eq) > 2:
        return False
    return sum(1 for _, is_action in cards_and_eq if is_action) <= 1


def _enumerate_hand(
    hand: dict[str, Card], incoming: int, dominate: bool, weights: ValueWeights
) -> list[tuple[tuple[str, ...], int, float]]:
    """Retorna [(subset, bloqueio, valor perdido)] viáveis para a mão."""
    keys = list(hand)
    if len(keys) > MAX_ENUM_CARDS:
        return _greedy_hand(hand, incoming, weights)
    out = []
    for size in range(len(keys) + 1):
        for subset in combinations(keys, size):
            block = sum(hand[k].defense or 0 for k in subset)
            lost = sum(card_value(hand[k], weights) for k in subset)
            if dominate and not _dominate_ok([(k, hand[k].is_non_attack_action) for k in subset]):
                continue
            out.append((subset, block, lost))
    return out


def _greedy_hand(
    hand: dict[str, Card], incoming: int, weights: ValueWeights
) -> list[tuple[tuple[str, ...], int, float]]:
    """Fallback para mãos grandes: bloqueia do menor custo-benefício ao maior."""
    ranked = sorted(hand, key=lambda k: card_value(hand[k], weights) / max(1, hand[k].defense or 0))
    chosen: list[str] = []
    for key in ranked:
        if sum(hand[k].defense or 0 for k in chosen) >= incoming:
            break
        chosen.append(key)
    block = sum(hand[k].defense or 0 for k in chosen)
    lost = sum(card_value(hand[k], weights) for k in chosen)
    return [((), 0, 0.0), (tuple(chosen), block, lost)]


def suggest_defense(
    incoming_damage: int,
    hand: dict[str, Card],
    equipment_defense: dict[str, int] | None = None,
    *,
    dominate: bool = False,
    top: int = 3,
    weights: ValueWeights = DEFAULT_WEIGHTS,
) -> list[DefenseOption]:
    """Sugere linhas de defesa ordenadas da melhor para a pior.

    - `hand`: apenas cartas que PODEM ser descartadas para bloquear (key -> Card).
    - `equipment_defense`: defesa ainda disponível por equipamento (uso "grátis",
      mas com microcusto para não desperdiçar a once-per-turn sem necessidade).
    - Sempre inclui a opção de não bloquear; nunca levanta erro por falta de opção.
    """
    equip = dict(equipment_defense or {})
    equip_options = [()]
    if equip:
        equip_keys = list(equip)
        equip_options = [
            combo for size in range(len(equip_keys) + 1) for combo in combinations(equip_keys, size)
        ]

    options: list[DefenseOption] = []
    for hand_subset, hand_block, hand_lost in _enumerate_hand(
        hand, incoming_damage, dominate, weights
    ):
        for eq_subset in equip_options:
            combined = [(k, False) for k in hand_subset] + [(k, False) for k in eq_subset]
            if dominate and not _dominate_ok(combined):
                continue
            eq_block = sum(equip[k] for k in eq_subset)
            block_total = hand_block + eq_block
            value_lost = hand_lost + EQUIPMENT_USE_COST * len(eq_subset)
            options.append(
                DefenseOption(
                    hand_cards=hand_subset,
                    equipment=eq_subset,
                    block_total=block_total,
                    damage_taken=max(0, incoming_damage - block_total),
                    value_lost=value_lost,
                )
            )
    options.sort(key=lambda o: (o.damage_taken, o.value_lost, len(o.hand_cards), len(o.equipment)))
    seen: set[tuple] = set()
    unique: list[DefenseOption] = []
    for opt in options:
        sig = (opt.hand_cards, opt.equipment)
        if sig not in seen:
            seen.add(sig)
            unique.append(opt)
    return unique[:top]
