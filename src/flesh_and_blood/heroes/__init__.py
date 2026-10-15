"""Arquitetura por herói: estratégias de planejamento e defesa.

Ponto de entrada: ``strategy_for(hero_key)`` devolve a ``HeroStrategy`` do
herói (ou a genérica, se não houver uma específica). Assim, bot, CLI e app
despacham SEM cadeias de ``if hero_key == ...`` espalhadas.
"""

from __future__ import annotations

from flesh_and_blood.heroes.base import HeroStrategy, TurnPlan, ward_base
from flesh_and_blood.heroes.bravo import (
    BRAVO_HEROES,
    BravoStrategy,
    CrushThreat,
    crush_threat,
    is_crush,
)
from flesh_and_blood.heroes.enigma import EnigmaStrategy, plan_enigma
from flesh_and_blood.heroes.generic import GenericStrategy, plan_generic_turn
from flesh_and_blood.heroes.matchups import (
    opponent_threat,
    phantasm_risk,
    threat_report,
)

__all__ = [
    "BRAVO_HEROES",
    "BravoStrategy",
    "CrushThreat",
    "EnigmaStrategy",
    "GenericStrategy",
    "HeroStrategy",
    "TurnPlan",
    "crush_threat",
    "is_crush",
    "opponent_threat",
    "phantasm_risk",
    "plan_enigma",
    "plan_generic_turn",
    "strategy_for",
    "threat_report",
    "ward_base",
]

_GENERIC = GenericStrategy()

_STRATEGIES: dict[str, HeroStrategy] = {
    "Enigma": EnigmaStrategy(),
    # Bravo em todas as suas faces registradas (todas jogam crush).
    **{key: BravoStrategy() for key in BRAVO_HEROES},
}


def strategy_for(hero_key: str) -> HeroStrategy:
    """Devolve a estratégia do herói; genérica quando não há específica."""
    return _STRATEGIES.get(hero_key, _GENERIC)
