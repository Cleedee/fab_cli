"""Estratégia genérica: heróis sem motor próprio (Briar, Kayo, Guardian etc.).

Usa o planejador burst/lethal de ``attack.plan_attack`` e normaliza o resultado
para o ``TurnPlan`` executável pelo bot.
"""

from __future__ import annotations

from flesh_and_blood.attack import plan_attack
from flesh_and_blood.heroes.base import HeroStrategy, TurnPlan
from flesh_and_blood.models import Card, GameState


def plan_generic_turn(
    state: GameState,
    side: str,
    cards: dict[str, Card],
    *,
    opponent_life: int | None = None,
) -> TurnPlan:
    """Planeja o turno com a arma do jogador e devolve um ``TurnPlan``."""
    p = state.players[side]
    weapon = p.weapons[0] if p.weapons else None
    ap = plan_attack(
        state,
        side,
        cards,
        opponent_life=opponent_life,
        weapon_key=weapon,
    )

    steps: list[tuple] = [("pitch", k) for k in ap.pitched]
    for key in ap.sequence:
        if weapon is not None and key == weapon:
            steps.append(("weapon", key))
        elif cards[key].is_attack:
            steps.append(("attack", key))
        else:
            steps.append(("play", key))
    steps.append(("resolve",))

    return TurnPlan(
        steps=steps,
        sequence=list(ap.sequence),
        pitched=list(ap.pitched),
        physical=ap.physical,
        arcane=ap.arcane,
        lethal=ap.lethal,
        notes=list(ap.notes),
        arsenal_suggestion=ap.arsenal_suggestion,
    )


class GenericStrategy(HeroStrategy):
    """Fallback para qualquer herói sem mecânica própria modelada."""

    hero_key = ""
    label = "genérico"

    def plan_turn(
        self,
        state: GameState,
        side: str,
        cards: dict[str, Card],
        *,
        opponent_life: int | None = None,
    ) -> TurnPlan:
        return plan_generic_turn(state, side, cards, opponent_life=opponent_life)
