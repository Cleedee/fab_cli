"""Estratégia e modelo de ameaça do Bravo (Guardian crush, Silver Age).

O Bravo assa um ataque com **crush** no arsenal e, no turno seguinte, usa a
habilidade do herói para virá-lo para cima com **+2{p}** e **Dominate**. O
``crush_threat`` estima esse golpe; parte do plano Enigma-vs-Bravo
(``docs/enigma_vs_bravo.md``) depende dessa estimativa.

Nota: ``BravoStrategy.plan_turn`` é MVP — reaproveita o plano genérico. O
objetivo desta fase é modelar a AMEAÇA do Bravo para o lado que o enfrenta.
"""

from __future__ import annotations

from dataclasses import dataclass

from flesh_and_blood.heroes.base import HeroStrategy, TurnPlan
from flesh_and_blood.heroes.generic import plan_generic_turn
from flesh_and_blood.models import Card, GameState, PlayerState

BRAVO_HEROES = (
    "Bravo",
    "Bravo, Flattering Showman",
    "Bravo, Showstopper",
    "Bravo, Star of the Show",
)

# A habilidade do herói vira a carta do arsenal e dá, se for crush: +2{p} e Dominate.
HERO_ABILITY_POWER_BONUS = 2
HERO_ABILITY_COST = 2


def is_crush(card: Card | None) -> bool:
    """Ataque com a palavra-chave crush (CR 8.4.2)."""
    return card is not None and card.is_attack and "crush" in card.text.lower()


def crush_effect(card: Card) -> str:
    """Trecho do texto a partir de 'crush' (o efeito de disrupção)."""
    low = card.text.lower()
    idx = low.find("crush")
    if idx < 0:
        return ""
    return " ".join(card.text[idx:].split())


@dataclass(frozen=True)
class CrushThreat:
    """Golpe de crush estimado do Bravo para o próximo turno."""

    card_key: str
    power: int  # poder base + bônus da habilidade do herói
    dominate: bool
    effect: str
    ready: bool  # há recursos (pitch) para custo + habilidade


def crush_threat(opp: PlayerState, cards: dict[str, Card]) -> CrushThreat | None:
    """Estima o crush que ``opp`` (Bravo) pode despejar no próximo turno.

    Retorna None se o arsenal não tiver um ataque com crush.
    """
    key = opp.arsenal
    if not key or key not in cards:
        return None
    card = cards[key]
    if not is_crush(card):
        return None
    power = (card.power or 0) + HERO_ABILITY_POWER_BONUS
    potential = opp.pitch_pool + sum((cards[k].pitch or 0) for k in opp.hand if k in cards)
    ready = potential >= (card.cost or 0) + HERO_ABILITY_COST
    return CrushThreat(
        card_key=key,
        power=power,
        dominate=True,
        effect=crush_effect(card),
        ready=ready,
    )


class BravoStrategy(HeroStrategy):
    """Estratégia do Bravo (crush). MVP: planeja como genérico."""

    hero_key = "Bravo, Flattering Showman"
    label = "Bravo (Guardian crush)"

    def plan_turn(
        self,
        state: GameState,
        side: str,
        cards: dict[str, Card],
        *,
        opponent_life: int | None = None,
    ) -> TurnPlan:
        plan = plan_generic_turn(state, side, cards, opponent_life=opponent_life)
        threat = crush_threat(state.players[side], cards)
        if threat is not None:
            plan.notes.append(
                f"Arsenal com crush ({threat.card_key}): prepara golpe "
                f"{threat.power}{{p}} Dominate no próximo turno."
            )
        return plan

    def hand_value_bonus(self, card: Card) -> float:
        # O payoff do deck é assar e despejar um crush: preservar na mão/arsenal.
        if is_crush(card):
            return 2.0
        return 0.0
