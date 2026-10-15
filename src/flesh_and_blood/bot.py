"""Política de decisão automática do bot.

O bot escolhe a estratégia do herói via ``heroes.strategy_for`` (Enigma,
Bravo, genérico...), planeja o turno e executa o ``TurnPlan`` passo a passo,
resolvendo cada elo na hora. Na defesa, usa ``defense.suggest_defense`` com o
bônus de valor específico do herói. A filosofia continua: apoio à decisão —
o bot escolhe a linha, o motor valida e tudo fica explícito no log.

Limitação do MVP: o bot resolve cada ataque na hora (assume que o oponente não
bloqueia). Para defender, o usuário usa `life` para ajustar manualmente.
"""

from __future__ import annotations

from flesh_and_blood import combat
from flesh_and_blood.defense import suggest_defense
from flesh_and_blood.heroes import strategy_for
from flesh_and_blood.heroes.base import TurnPlan
from flesh_and_blood.heroes.enigma import (
    ASTRAL_ETCHINGS,
    SECOND_TENET,
    TRANSCEND_CARDS,
)
from flesh_and_blood.models import Card, Color, GameState

ENGINE_CARDS = ("Spectral Manifestations", "Solitary Companion")


def run_bot_turn(state: GameState, side: str, cards: dict[str, Card]) -> list[str]:
    """Executa o turno do bot do lado indicado; retorna o log de ações."""
    p = state.players[side]
    strategy = strategy_for(p.hero_key)
    plan = strategy.plan_turn(state, side, cards)
    log = _execute_plan(state, side, cards, plan)
    # Fim da janela de ação: o bot passa a prioridade (2º passe resolve).
    for notice in combat.pass_priority(state, side, cards):
        log.append(notice.text)
    return log


def _resolve_clean(state: GameState, cards: dict[str, Card], log: list[str]) -> None:
    """Resolve o elo aberto mais recente e anexa as mensagens ao log."""
    try:
        result = combat.resolve_link(state, cards)
    except combat.CombatError as err:
        log.append(f"AVISO ao resolver: {err}")
        return
    for notice in result["notices"]:
        log.append(notice.text)
    if result["physical"]:
        log.append(f"Dano físico {result['physical']} aplicado a {result['defender']}.")
    if result["arcane"]:
        log.append(f"Dano arcano {result['arcane']} aplicado a {result['defender']}.")


def _execute_plan(state: GameState, side: str, cards: dict[str, Card], plan: TurnPlan) -> list[str]:
    """Executa um ``TurnPlan`` genérico (vocabulário de steps unificado)."""
    log: list[str] = []
    blue_pitched = any(cards[k].color == Color.BLUE for k in plan.pitched)
    transcended = False

    for raw_step in plan.steps:
        step, key = raw_step if len(raw_step) == 2 else (raw_step[0], None)
        try:
            if step == "pitch":
                gained = combat.pitch(state, side, key, cards)
                log.append(f"Pitch de {key} (+{gained} recurso).")
            elif step == "activate_enigma":
                notice = combat.activate_hero_ability(state, side, cards)
                log.append(notice.text)
            elif step == "play":
                card = cards[key]
                is_instant = "Instant" in card.types and "Action" not in card.types
                if is_instant:
                    counters = 1 if "Waxing Specter" in card.name and blue_pitched else 0
                    notice = combat.play_instant_aura(
                        state, side, key, cards, counters_on_enter=counters
                    )
                    log.append(notice.text)
                    if card.name in TRANSCEND_CARDS:
                        transcended = True
                elif card.name in ENGINE_CARDS:
                    for notice in combat.play_aura_engine(state, side, key, cards):
                        log.append(notice.text)
                    _resolve_clean(state, cards, log)
                elif card.name == ASTRAL_ETCHINGS:
                    for notice in combat.astral_charge(state, side, cards):
                        log.append(notice.text)
                    _resolve_clean(state, cards, log)
                else:
                    for notice in combat.play_action(state, side, key, cards):
                        log.append(notice.text)
                    _resolve_clean(state, cards, log)
            elif step == "cosmo":
                link = combat.attack_with_aura(state, side, key, cards)
                log.append(f"Cosmo ataca com a aura {key} ({link.total_damage} de dano).")
                _resolve_clean(state, cards, log)
            elif step == "weapon":
                combat.declare_attack(state, side, key, cards, is_weapon=True, resource_cost=1)
                log.append(f"Ataque de arma {key}.")
                _resolve_clean(state, cards, log)
            elif step == "attack":
                c = cards[key]
                bonus = 2 if transcended and c.name.startswith(SECOND_TENET) else 0
                link = combat.declare_attack(state, side, key, cards, power_counters=bonus)
                if bonus:
                    log.append(f"{c.name}: +2 por transcend.")
                log.append(f"Ataque de {c.name} ({link.total_damage} de dano).")
                _resolve_clean(state, cards, log)
            elif step == "resolve":
                pass
        except combat.CombatError as err:
            log.append(f"AVISO: {err} (plano: {step} {key}).")
    return log


def choose_bot_defense(state: GameState, def_side: str, cards: dict[str, Card]) -> list[str]:
    """Escolhe e aplica a melhor defesa disponível para o lado indicado."""
    log: list[str] = []
    p = state.players[def_side]
    opp_side = state.opponent_of(def_side)
    link = combat.current_link(state, opp_side)
    if link is None:
        return ["Nada aberto para defender."]

    strategy = strategy_for(p.hero_key)

    hand: dict[str, Card] = {k: cards[k] for k in p.hand if k in cards}
    equip: dict[str, int] = {}
    for k in p.equipment_uses:
        if k in p.equipment_destroyed or k in p.equipment_used_this_turn:
            continue
        c = cards.get(k)
        if c is not None and c.is_equipment and (c.defense or 0) > 0:
            equip[k] = c.defense

    options = suggest_defense(
        link.damage_remaining,
        hand,
        equip,
        dominate=link.dominate,
        top=1,
        value_bonus=strategy.hand_value_bonus,
    )
    best = options[0]

    log.extend(strategy.defense_notes(state, def_side, cards, link))

    if not best.hand_cards and not best.equipment:
        return ["Bot não defende (economiza a mão)."]

    for notice in combat.defend_link(state, def_side, list(best.hand_cards), cards):
        log.append(notice.text)
    for eq in best.equipment:
        gained = combat.use_equipment_defense(state, def_side, eq, cards)
        log.append(f"Equipamento {eq} usado (+{gained} defesa).")
    log.append(
        f"Bot defendeu com {', '.join(best.hand_cards) or 'equipamento'}: -{best.block_total} de dano."
    )
    return log
