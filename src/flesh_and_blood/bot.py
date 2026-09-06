"""Política de decisão automática do bot (Fase 5b — Enigma).

O bot executa um turno completo (pitch, motor Enigma, ataques via Cosmo e
resolução imediata de cada elo) usando o planejador de `attack.py`; na defesa,
usa o sugeridor de `defense.py`. A filosofia continua a mesma: apoio à decisão
— o bot escolhe a linha, o motor valida e tudo fica explícito no log.

Limitação do MVP: o bot resolve cada ataque na hora (assume que o oponente não
bloqueia). Se o usuário quiser defender, usa `life` para ajustar manualmente.
"""

from __future__ import annotations

from flesh_and_blood import combat
from flesh_and_blood.attack import plan_attack, plan_enigma
from flesh_and_blood.defense import suggest_defense
from flesh_and_blood.models import Card, Color, GameState

ENGINE_CARDS = ("Spectral Manifestations", "Solitary Companion")
ASTRAL_ETCHINGS = "Astral Etchings"


def run_bot_turn(state: GameState, side: str, cards: dict[str, Card]) -> list[str]:
    """Executa o turno do bot do lado indicado; retorna o log de ações."""
    p = state.players[side]
    if p.hero_key == "Enigma":
        log = _run_enigma_turn(state, side, cards)
    else:
        log = _run_generic_turn(state, side, cards)
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


def _run_enigma_turn(state: GameState, side: str, cards: dict[str, Card]) -> list[str]:
    plan = plan_enigma(state, side, cards)
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
                    name = card.name
                    counters = 1 if "Waxing Specter" in name and blue_pitched else 0
                    notice = combat.play_instant_aura(
                        state, side, key, cards, counters_on_enter=counters
                    )
                    log.append(notice.text)
                    if name in ("Homage to Ancestors", "Pass Over", "Preserve Tradition"):
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
            elif step == "attack":
                c = cards[key]
                bonus = 2 if transcended and c.name.startswith("Second Tenet of Chi") else 0
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


def _run_generic_turn(state: GameState, side: str, cards: dict[str, Card]) -> list[str]:
    """Turno genérico para heróis sem motor próprio (usa plan_attack)."""
    p = state.players[side]
    weapon = p.weapons[0] if p.weapons else None
    plan = plan_attack(state, side, cards, weapon_key=weapon)
    log: list[str] = []
    if plan.pitched:
        for key in plan.pitched:
            gained = combat.pitch(state, side, key, cards)
            log.append(f"Pitch de {key} (+{gained} recurso).")
    for key in plan.sequence:
        try:
            card = cards[key]
            if key == weapon:
                combat.declare_attack(state, side, key, cards, is_weapon=True, resource_cost=1)
                log.append(f"Ataque de arma {key}.")
            elif card.is_attack:
                combat.declare_attack(state, side, key, cards)
                log.append(f"Ataque de {card.name}.")
            else:
                for notice in combat.play_action(state, side, key, cards):
                    log.append(notice.text)
                _resolve_clean(state, cards, log)
                continue
            _resolve_clean(state, cards, log)
        except combat.CombatError as err:
            log.append(f"AVISO: {err}")
    return log


def choose_bot_defense(state: GameState, def_side: str, cards: dict[str, Card]) -> list[str]:
    """Escolhe e aplica a melhor defesa disponível para o lado indicado."""
    log: list[str] = []
    p = state.players[def_side]
    opp_side = state.opponent_of(def_side)
    link = combat.current_link(state, opp_side)
    if link is None:
        return ["Nada aberto para defender."]

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
    )
    best = options[0]
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
