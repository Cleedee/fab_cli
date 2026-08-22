"""Operações de turno e combate (Fase 1).

Filosofia: o usuário declara o que acontece; o motor valida, faz a matemática
e devolve "notices" — lembretes de triggers que precisam de decisão manual
(on-hit, arcano, ward). Não é um validador completo de regras.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import Card, ChainLink, GameState, PlayerState

EMBODIMENT_EARTH = "Embodiment of Earth"
EMBODIMENT_LIGHTNING = "Embodiment of Lightning"
SPECTRAL_SHIELD = "Spectral Shield"


class CombatError(Exception):
    """Ação ilegal ou inconsistente com o estado."""


@dataclass
class Notice:
    """Lembrete de trigger/efeito para o jogador decidir."""

    text: str
    source_key: str | None = None


# ---------------------------------------------------------------------------
# Turno
# ---------------------------------------------------------------------------


def start_turn(state: GameState, side: str) -> list[Notice]:
    """Inicia o turno do lado indicado e reseta contadores por turno."""
    notices: list[Notice] = []
    p = state.players[side]
    state.active_player = side
    state.turn += 1
    p.action_points = 1
    p.hero_ability_used = False
    p.equipment_used_this_turn.clear()
    p.non_attack_actions_played = 0
    p.weapon_attacks_this_turn.clear()
    p.first_attack_damage_done = False
    p.cards_played_this_turn.clear()

    # Embodiment of Earth é destruído no início da sua action phase.
    while p.auras.get(EMBODIMENT_EARTH):
        p.pop_aura(EMBODIMENT_EARTH)
        notices.append(Notice(f"{EMBODIMENT_EARTH} destruído (início da action phase)."))
    return notices


def end_turn(state: GameState) -> None:
    """Encerra o turno e passa para o oponente (compra é manual por enquanto)."""
    state.active_player = state.opponent_of(state.active_player)


# ---------------------------------------------------------------------------
# Recursos e mão
# ---------------------------------------------------------------------------


def pitch(state: GameState, side: str, card_key: str, cards: dict[str, Card]) -> int:
    """Dá pitch numa carta da mão; recursos vão para o pool."""
    card = _require(cards, card_key)
    if card.pitch is None:
        raise CombatError(f"{card.name} não tem valor de pitch")
    _move_card(state.players[side].hand, card_key)
    state.players[side].pitch_pool += card.pitch
    return card.pitch


def place_arsenal(state: GameState, side: str, card_key: str) -> None:
    """Coloca uma carta da mão no arsenal (uma vez por turno)."""
    p = state.players[side]
    if p.arsenal is not None:
        raise CombatError("arsenal já ocupado")
    _move_card(p.hand, card_key)
    p.arsenal = card_key


# ---------------------------------------------------------------------------
# Jogando cartas
# ---------------------------------------------------------------------------


def play_action(
    state: GameState,
    side: str,
    card_key: str,
    cards: dict[str, Card],
    *,
    go_again_earned: bool | None = None,
) -> list[Notice]:
    """Joga uma non-attack action da mão (Defense Reaction não passa por aqui).

    go_again_earned: None = deduz das keywords da carta; passe False quando o
    Go Again for condicional e não satisfeito, True quando concedido por outro
    efeito.
    """
    notices: list[Notice] = []
    p = state.players[side]
    card = _require(cards, card_key)
    if "Defense Reaction" in card.types:
        raise CombatError("Defense Reaction é jogada durante a defesa")
    if not card.is_non_attack_action:
        raise CombatError(f"{card.name} não é uma non-attack action")
    if card_key not in p.hand:
        raise CombatError(f"{card.name} não está na mão")

    cost = card.cost or 0
    if p.pitch_pool < cost:
        raise CombatError(f"recursos insuficientes ({p.pitch_pool} < {cost})")

    has_go_again = any(kw == "Go again" for kw in card.keywords)
    earned = has_go_again if go_again_earned is None else go_again_earned
    _use_ap(p, earned)

    p.pitch_pool -= cost
    _move_card(p.hand, card_key)
    p.cards_played_this_turn.append(card_key)
    p.non_attack_actions_played += 1

    # Briar: a 2ª non-attack action do turno cria Embodiment of Lightning.
    if p.hero_key.startswith("Briar") and p.non_attack_actions_played == 2:
        p.add_aura(EMBODIMENT_LIGHTNING)
        notices.append(Notice(f"Briar criou {EMBODIMENT_LIGHTNING} (2ª non-attack action)."))
    return notices


# ---------------------------------------------------------------------------
# Ataques
# ---------------------------------------------------------------------------


def declare_attack(
    state: GameState,
    side: str,
    card_key: str,
    cards: dict[str, Card],
    *,
    is_weapon: bool = False,
    resource_cost: int = 0,
    go_again_earned: bool | None = None,
    power_counters: int = 0,
    dominate: bool = False,
) -> ChainLink:
    """Declara um ataque e cria um chain link.

    - Attack action: paga o custo, sai da mão/arsenal e consome 1 AP (devolvido
      se ganhar Go Again). Embodiment of Lightning é consumido automaticamente
      para conceder Go Again à próxima attack action.
    - Arma (is_weapon): uma vez por turno; custo em recursos via resource_cost
      (ex.: Star Fall custa 1, ou 0 se Blossom of Spring foi destruída).
    - power_counters: contadores +1{p} já existentes no atacante.
    """
    p = state.players[side]
    card = _require(cards, card_key)

    if is_weapon:
        if not card.is_weapon:
            raise CombatError(f"{card.name} não é uma arma")
        if card_key in p.weapon_attacks_this_turn:
            raise CombatError(f"{card.name} já atacou este turno")
        # Arma também consome o AP do turno ("Once per Turn Action");
        # Go Again concedido por efeito (ex.: Star Fall com Lightning jogado).
        _use_ap(p, bool(go_again_earned))
        total_cost = resource_cost or 0
        if p.pitch_pool < total_cost:
            raise CombatError(f"recursos insuficientes ({p.pitch_pool} < {total_cost})")
        p.pitch_pool -= total_cost
        p.weapon_attacks_this_turn.append(card_key)
        total = (card.power or 0) + power_counters

    else:
        if not card.is_attack:
            raise CombatError(f"{card.name} não é uma attack action")
        from_arsenal = card_key == p.arsenal
        if card_key not in p.hand and not from_arsenal:
            raise CombatError(f"{card.name} não está na mão nem no arsenal")

        # Embodiment of Lightning: a próxima attack action ganha Go Again.
        granted_by_aura = bool(p.auras.get(EMBODIMENT_LIGHTNING))
        if granted_by_aura:
            p.pop_aura(EMBODIMENT_LIGHTNING)

        innate = any(kw == "Go again" for kw in card.keywords)
        earned = (
            (innate or granted_by_aura)
            if go_again_earned is None
            else (go_again_earned or granted_by_aura)
        )
        _use_ap(p, earned)

        cost = card.cost or 0
        if p.pitch_pool < cost:
            raise CombatError(f"recursos insuficientes ({p.pitch_pool} < {cost})")
        p.pitch_pool -= cost
        if from_arsenal:
            p.arsenal = None
        else:
            _move_card(p.hand, card_key)
        p.cards_played_this_turn.append(card_key)
        total = (card.power or 0) + power_counters

    link = ChainLink(attacker=side, card_key=card_key, total_damage=total, dominate=dominate)
    state.chain.append(link)
    return link


def boost_link(state: GameState, side: str, amount: int, source_key: str | None = None) -> Notice:
    """Aplica um boost (+X{p}) ao link aberto do lado atacante."""
    link = current_link(state, side)
    if link is None:
        raise CombatError("nenhum chain link aberto para receber boost")
    link.total_damage += amount
    src = f" ({source_key})" if source_key else ""
    return Notice(f"+{amount} power no ataque{src}.", source_key)


def set_arcane_on_link(state: GameState, side: str, amount: int, source_key: str | None) -> Notice:
    """Registra dano arcano pertencente ao ataque atual (ex.: fusão de Shockwave)."""
    link = current_link(state, side)
    if link is None:
        raise CombatError("nenhum chain link aberto para registrar arcano")
    link.arcane_damage += amount
    return Notice(f"+{amount} de dano arcano no ataque ({source_key}).", source_key)


def current_link(state: GameState, side: str) -> ChainLink | None:
    for link in reversed(state.chain):
        if link.attacker == side and not link.resolved:
            return link
    return None


# ---------------------------------------------------------------------------
# Defesa
# ---------------------------------------------------------------------------


def defend_link(
    state: GameState,
    defender_side: str,
    card_keys: list[str],
    cards: dict[str, Card],
) -> list[Notice]:
    """Defende o link aberto do oponente com cartas da mão.

    Embodiment of Earth dá +1{d} a cada non-attack action defendendo.
    Retorna notices (ex.: Stinging Sprite defendendo causa 1 arcano).
    """
    notices: list[Notice] = []
    defender = state.players[defender_side]
    attacker_side = state.opponent_of(defender_side)
    link = current_link(state, attacker_side)
    if link is None:
        raise CombatError("nenhum chain link aberto do oponente")

    if link.dominate and len(card_keys) > 2:
        raise CombatError("Dominate: máximo de 2 cartas na defesa")
    if link.dominate:
        n_actions = sum(
            1 for k in card_keys if (c := cards.get(k)) is not None and "Action" in c.types
        )
        if n_actions > 1:
            raise CombatError("Dominate: no máximo 1 action card na defesa")

    earth_bonus_active = bool(defender.auras.get(EMBODIMENT_EARTH))
    block_total = 0
    for key in card_keys:
        card = _require(cards, key)
        if key not in defender.hand:
            raise CombatError(f"{card.name} não está na sua mão")
        defense = card.defense or 0
        if earth_bonus_active and card.is_non_attack_action:
            defense += 1
        block_total += defense
        _move_card(defender.hand, key)
        low_text = card.text.lower()
        if "attacks or defends" in low_text and "arcane damage" in low_text:
            notices.append(Notice(f"{card.name} defendeu: 1 arcano ao atacante.", key))

    link.blocked_by.extend(card_keys)
    link.blocked_damage += block_total
    return notices


def use_equipment_defense(
    state: GameState,
    defender_side: str,
    equip_key: str,
    cards: dict[str, Card],
    extra_defense: int = 0,
) -> int:
    """Usa um equipamento para defender (uma vez por turno por peça).

    extra_defense: bônus condicional informado pelo usuário
    (ex.: Blade Beckoner contra arma vale +1).
    """
    defender = state.players[defender_side]
    link = current_link(state, state.opponent_of(defender_side))
    if link is None:
        raise CombatError("nenhum chain link aberto do oponente")
    card = _require(cards, equip_key)
    if not card.is_equipment:
        raise CombatError(f"{card.name} não é equipamento")
    if equip_key in defender.equipment_destroyed:
        raise CombatError(f"{card.name} está destruído")
    if equip_key in defender.equipment_used_this_turn:
        raise CombatError(f"{card.name} já foi usado neste turno")
    defender.equipment_used_this_turn.append(equip_key)
    gained = (card.defense or 0) + extra_defense
    link.blocked_by.append(equip_key)
    link.blocked_damage += gained
    return gained


# ---------------------------------------------------------------------------
# Ward (Enigma), arcano e resolução
# ---------------------------------------------------------------------------


def ward_value(player: PlayerState, aura_key: str) -> int:
    """Ward total somando todas as cópias da aura (1 + contadores cada)."""
    return sum(1 + counters for counters in player.auras.get(aura_key, []))


def spend_ward(state: GameState, defender_side: str, aura_key: str, needed: int) -> list[Notice]:
    """Destrói cópias da aura (maior contador primeiro) prevenindo até 'needed'.

    Tokens como Spectral Shield somem; auras de carta vão para o graveyard.
    O valor prevenido deve ser descontado manualmente em resolve_link
    (ward_prevented), mantendo o fluxo explícito para o jogador.
    """
    notices: list[Notice] = []
    defender = state.players[defender_side]
    prevented = 0
    while prevented < needed and defender.auras.get(aura_key):
        copies = defender.auras[aura_key]
        best = max(range(len(copies)), key=lambda i: copies[i])
        counters = defender.pop_aura(aura_key, best)
        assert counters is not None
        value = 1 + counters
        prevented += value
        if aura_key == SPECTRAL_SHIELD:
            notices.append(Notice(f"Spectral Shield (+{counters}) destruído: previne {value}."))
        else:
            defender.graveyard.append(aura_key)
            notices.append(Notice(f"{aura_key} (+{counters}) destruído: previne {value}."))
    return notices


def deal_arcane(
    state: GameState,
    target_side: str,
    amount: int,
    *,
    prevented: int = 0,
) -> int:
    """Dano arcano direto (Arcane Barrier/spellvoid são manuais via 'prevented')."""
    actual = max(0, amount - max(0, prevented))
    state.players[target_side].damage(actual)
    return actual


def resolve_link(
    state: GameState,
    cards: dict[str, Card],
    *,
    ward_prevented: int = 0,
    arcane_prevented: int = 0,
) -> dict:
    """Resolve o link aberto mais recente: aplica dano e gera notices."""
    link = next((l for l in reversed(state.chain) if not l.resolved), None)
    if link is None:
        raise CombatError("nenhum chain link para resolver")

    attacker = state.players[link.attacker]
    defender_side = state.opponent_of(link.attacker)
    defender = state.players[defender_side]
    attacked_card = cards.get(link.card_key)

    physical = max(0, link.damage_remaining - max(0, ward_prevented))
    arcane = max(0, link.arcane_damage - max(0, arcane_prevented))

    notices: list[Notice] = []
    if physical:
        defender.damage(physical)
    if arcane:
        defender.damage(arcane)

    if physical > 0 and attacked_card is not None:
        notices.append(Notice(f"On-hit de {attacked_card.name}: conferir efeitos.", link.card_key))
        if "when this hits" in attacked_card.text.lower():
            notices.append(
                Notice(f"Efeito on-hit de {attacked_card.name}: '{attacked_card.text}'.")
            )

    # Briar: primeira vez no turno que uma attack ACTION causa dano ao herói oposto
    # (físico do ataque ou o arcano dele) cria Embodiment of Earth. Armas não contam.
    is_attack_action = bool(
        attacked_card and attacked_card.is_attack and "Action" in attacked_card.types
    )
    dealt_some = physical > 0 or arcane > 0
    if (
        attacker.hero_key.startswith("Briar")
        and is_attack_action
        and dealt_some
        and not attacker.first_attack_damage_done
    ):
        attacker.first_attack_damage_done = True
        if not attacker.auras.get(EMBODIMENT_EARTH):
            attacker.add_aura(EMBODIMENT_EARTH)
            notices.append(Notice(f"Briar criou {EMBODIMENT_EARTH} (attack action causou dano)."))

    link.resolved = True
    return {
        "physical": physical,
        "arcane": arcane,
        "hit": physical > 0,
        "defender": defender_side,
        "notices": notices,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require(cards: dict[str, Card], key: str) -> Card:
    card = cards.get(key)
    if card is None:
        raise CombatError(f"carta desconhecida: {key}")
    return card


def _use_ap(p: PlayerState, earned_go_again: bool) -> None:
    """Gasta 1 AP (obrigatório para qualquer action/ataque de arma).

    Go Again devolve o AP depois — logo, cartas com Go Again são neutras.
    """
    if p.action_points <= 0:
        raise CombatError("sem action points disponíveis")
    p.action_points -= 1
    if earned_go_again:
        p.action_points += 1


def _move_card(pile: list[str], card_key: str) -> None:
    if card_key not in pile:
        raise CombatError(f"'{card_key}' não está onde deveria estar")
    pile.remove(card_key)
