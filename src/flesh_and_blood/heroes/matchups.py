"""Modelos de ameaça por oponente (matchup) e utilitários de leitura de mesa.

Reúne heurísticas que valem para QUALQUER herói que enfrente o oponente:

- ``phantasm_risk``: o oponente tem attack action não-Illusionist com 6+{p}
  na mão/arsenal — pode destruir seus ataques com Phantasm (CR 8.3.13).
- ``opponent_threat``: estimativa da ameaça do próximo turno (hoje, o crush
  do Bravo). Despacha por herói do oponente.
"""

from __future__ import annotations

from flesh_and_blood.heroes.bravo import BRAVO_HEROES, CrushThreat, crush_threat
from flesh_and_blood.models import Card, GameState, PlayerState

PHANTASM_POWER_THRESHOLD = 6


def phantasm_risk(opp: PlayerState, cards: dict[str, Card]) -> str | None:
    """Retorna a chave da carta do oponente que pode popar Phantasm, ou None.

    Phantasm (CR 8.3.13): seu ataque é destruído se defendido por uma attack
    action card não-Illusionist com 6+{p}. Checamos mão + arsenal do oponente.
    """
    pool = list(opp.hand)
    if opp.arsenal:
        pool.append(opp.arsenal)
    for key in pool:
        card = cards.get(key)
        if card is None or not card.is_attack:
            continue
        if "Illusionist" in card.types:
            continue
        if (card.power or 0) >= PHANTASM_POWER_THRESHOLD:
            return key
    return None


def opponent_threat(state: GameState, side: str, cards: dict[str, Card]) -> CrushThreat | None:
    """Ameaça estimada do oponente para o próximo turno (hoje: crush do Bravo)."""
    opp = state.players[state.opponent_of(side)]
    if opp.hero_key in BRAVO_HEROES:
        return crush_threat(opp, cards)
    return None


def threat_report(state: GameState, side: str, cards: dict[str, Card]) -> list[str]:
    """Linhas de aviso sobre a ameaça do oponente (para log/planejamento)."""
    lines: list[str] = []
    opp = state.players[state.opponent_of(side)]

    threat = opponent_threat(state, side, cards)
    if threat is not None:
        ready = "pronto" if threat.ready else "recursos incertos"
        lines.append(
            f"AMEAÇA: crush {threat.card_key} — {threat.power}{{p}} Dominate "
            f"({ready}). Prevenir/ward para manter o dano < 4 e desligar o crush."
        )

    popper = phantasm_risk(opp, cards)
    if popper is not None:
        lines.append(
            f"PHANTASM: {popper} ({cards[popper].power}{{p}}) pode destruir seus "
            f"ataques com Phantasm; prefira Clear Conscience / ataques de aura."
        )
    return lines
