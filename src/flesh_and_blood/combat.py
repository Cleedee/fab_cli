"""Operações de turno e combate (Fase 1).

Filosofia: o usuário declara o que acontece; o motor valida, faz a matemática
e devolve "notices" — lembretes de triggers que precisam de decisão manual
(on-hit, arcano, ward). Não é um validador completo de regras.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import Card, ChainLink, Color, GameState, PlayerState

EMBODIMENT_EARTH = "Embodiment of Earth"
EMBODIMENT_LIGHTNING = "Embodiment of Lightning"
SPECTRAL_SHIELD = "Spectral Shield"

# Heróis com a passiva watery grave (jogar cartas do cemitério).
GRAVY_BONES_HEROES: frozenset[str] = frozenset({"Gravy Bones", "Gravy Bones, Shipwrecked Looter"})


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
    state.priority = side
    state.passes = 0
    p.action_points = 1
    p.hero_ability_used = False
    p.equipment_used_this_turn.clear()
    p.non_attack_actions_played = 0
    p.weapon_attacks_this_turn.clear()
    p.spectral_attacks_this_turn = 0
    p.first_attack_damage_done = False
    p.cards_played_this_turn.clear()
    p.blue_to_graveyard_this_turn = 0

    # Embodiment of Earth é destruído no início da sua action phase.
    while p.auras.get(EMBODIMENT_EARTH):
        p.pop_aura(EMBODIMENT_EARTH)
        notices.append(Notice(f"{EMBODIMENT_EARTH} destruído (início da action phase)."))

    # --- Tokens: triggers de início de turno ---
    # Might: destrói, próximo ataque +1{p}
    if has_aura(p, TOKEN_MIGHT):
        p.pop_aura(TOKEN_MIGHT)
        notices.append(Notice(f"{TOKEN_MIGHT} destruído: próximo ataque +1{{p}}."))

    # Agility: destrói, próximo ataque Go Again
    if has_aura(p, TOKEN_AGILITY):
        p.pop_aura(TOKEN_AGILITY)
        notices.append(Notice(f"{TOKEN_AGILITY} destruído: próximo ataque Go Again."))

    # Vigor: destrói, +1{r}
    if has_aura(p, TOKEN_VIGOR):
        p.pop_aura(TOKEN_VIGOR)
        p.pitch_pool += 1
        notices.append(Notice(f"{TOKEN_VIGOR} destruído: +1{{r}}."))

    # Toughness: no início do turno do oponente, destrói e dá +1{d} na próxima defesa
    opponent = state.players[state.opponent_of(side)]
    if has_aura(opponent, TOKEN_TOUGHNESS):
        opponent.pop_aura(TOKEN_TOUGHNESS)
        notices.append(Notice(f"{TOKEN_TOUGHNESS} (oponente) destruído: próxima defesa +1{{d}}."))

    return notices


def end_turn(state: GameState) -> list[Notice]:
    """Encerra o turno e passa para o oponente. Retorna lembretes de triggers."""
    notices: list[Notice] = []
    p = state.players[state.active_player]

    # --- Tokens: triggers fim de turno ---
    # Ponder: destrói, compre 1 carta
    if has_aura(p, TOKEN_PONDER):
        p.pop_aura(TOKEN_PONDER)
        notices.append(Notice(f"{TOKEN_PONDER} destruído: compre 1 carta."))

    # Bloodrot Pox: 2{d} ou pagar {r}{r}{r}
    if has_aura(p, TOKEN_BLOODROT_POX):
        notices.append(Notice(f"{TOKEN_BLOODROT_POX}: pague {{r}}{{r}}{{r}} ou receba 2{{d}}."))

    # Inertia: bottom hand+arsenal
    if has_aura(p, TOKEN_INERTIA):
        p.pop_aura(TOKEN_INERTIA)
        notices.append(Notice(f"{TOKEN_INERTIA}: coloque mão+arsenal no fundo do deck."))

    # Frostbite: destrói no fim de turno
    if has_aura(p, TOKEN_FROSTBITE):
        p.pop_aura(TOKEN_FROSTBITE)
        notices.append(Notice(f"{TOKEN_FROSTBITE} destruído (fim de turno)."))

    # Frailty: destrói no fim de turno
    if has_aura(p, TOKEN_FRAILTY):
        p.pop_aura(TOKEN_FRAILTY)
        notices.append(Notice(f"{TOKEN_FRAILTY} destruído (fim de turno)."))

    state.active_player = state.opponent_of(state.active_player)
    return notices


# ---------------------------------------------------------------------------
# Prioridade
# ---------------------------------------------------------------------------


def give_priority(state: GameState, side: str) -> None:
    """Transfere a palavra para `side`, zerando a contagem de passes.

    Sem validação (filosofia de apoio): o app emite AVISO se alguém agir fora
    da sua prioridade, mas não bloqueia o override manual.
    """
    state.priority = side
    state.passes = 0


def pass_priority(state: GameState, side: str, cards: dict[str, Card]) -> list[Notice]:
    """Lado `side` passa a prioridade.

    - Fora da prioridade: AVISO, mas o passe é contado (filosofia manual).
    - 1º passe: devolve a palavra ao oponente (janela continua aberta).
    - 2º passe consecutivo: resolve o topo da corrente automaticamente e
      devolve a palavra ao jogador ativo (nova janela).
    """
    notices: list[Notice] = []
    if state.priority is not None and state.priority != side:
        notices.append(Notice(f"Aviso: prioridade é de {state.priority}, não de {side} (manual)."))
    state.passes += 1
    open_link = next((l for l in reversed(state.chain) if not l.resolved), None)
    if state.passes >= 2 and open_link is not None:
        result = resolve_link(state, cards)
        notices.extend(result["notices"])
        notices.append(
            Notice(
                f"Ambos passaram: link resolvido "
                f"({result['physical']} físico, {result['arcane']} arcano)."
            )
        )
        state.priority = state.active_player
        state.passes = 0
        return notices
    if state.passes >= 2:
        state.priority = state.active_player
        state.passes = 0
        return notices
    state.priority = state.opponent_of(side)
    return notices


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


def draw_from_deck(state: GameState, side: str) -> Notice:
    """Compra a carta do topo do deck (regras) para a mão.

    Deck em `PlayerState.deck` (topo = índice 0), preenchido por auto_setup ou
    pelo comando `deck`. Retorna Notice do que foi comprado.
    """
    p = state.players[side]
    if not p.deck:
        raise CombatError("deck vazio — use 'deck <lado> <arquivo>' ou 'draw <carta>' manual")
    key = p.deck.pop(0)
    p.hand.append(key)
    return Notice(f"{side} comprou do topo: {key}.")


def place_arsenal(state: GameState, side: str, card_key: str) -> None:
    """Coloca uma carta da mão no arsenal (uma vez por turno)."""
    p = state.players[side]
    if p.arsenal is not None:
        raise CombatError("arsenal já ocupado")
    _move_card(p.hand, card_key)
    p.arsenal = card_key


def discard(
    state: GameState, side: str, card_key: str, cards: dict[str, Card] | None = None
) -> None:
    """Descarta uma carta da mão para o cemitério.

    Um card blue entrando no cemitério neste turno alimenta a condição do
    Gravy Bones (jogar cards watery grave do cemitério).
    """
    p = state.players[side]
    _move_card(p.hand, card_key)
    p.graveyard.append(card_key)
    if cards is not None:
        card = cards.get(card_key)
        if card is not None and card.color == Color.BLUE:
            p.blue_to_graveyard_this_turn += 1


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------

# Nomes dos tokens mais comuns (constantes para referência)
TOKEN_GOLD = "Gold"
TOKEN_SILVER = "Silver"
TOKEN_COPPER = "Copper"
TOKEN_MIGHT = "Might"
TOKEN_COURAGE = "Courage"
TOKEN_PONDER = "Ponder"
TOKEN_VIGOR = "Vigor"
TOKEN_AGILITY = "Agility"
TOKEN_QUICKEN = "Quicken"
TOKEN_ELOQUENCE = "Eloquence"
TOKEN_RUNECHANT = "Runechant"
TOKEN_TOUGHNESS = "Toughness"
TOKEN_FROSTBITE = "Frostbite"
TOKEN_FRAILTY = "Frailty"
TOKEN_BLOODROT_POX = "Bloodrot Pox"
TOKEN_INERTIA = "Inertia"

# Custo de ativação de itens (Gold/Silver/Copper → comprar 1 carta)
ITEM_TOKEN_COSTS: dict[str, int] = {
    TOKEN_GOLD: 2,
    TOKEN_SILVER: 3,
    TOKEN_COPPER: 4,
}


def create_token(
    state: GameState,
    side: str,
    name: str,
    qty: int = 1,
    cards: dict[str, Card] | None = None,
) -> Notice:
    """Cria token/aura/permanente pelo nome.

    - item (Gold/Silver/Copper) → tokens;
    - carta real com tipo permanente (Ally/Item/Landmark) → permanentes;
    - senão → aura.
    """
    card = state.players[side]
    if name in ITEM_TOKEN_COSTS:
        card.add_token(name, qty)
        return Notice(f"+{qty} {name} (item)")
    if cards is not None:
        real = cards.get(name)
        if real is not None and real.is_permanent:
            for _ in range(qty):
                card.add_permanent(name)
            return Notice(f"+{qty} {name} (permanente)")
    for _ in range(qty):
        card.add_aura(name)
    return Notice(f"+{qty} {name} (aura)")


def remove_token(state: GameState, side: str, name: str, qty: int = 1) -> Notice:
    """Remove token/aura/permanente. Procura nas três zonas."""
    p = state.players[side]
    if name in ITEM_TOKEN_COSTS:
        remaining = p.pop_token(name, qty)
        removed = qty - remaining if remaining < qty else 0
        return Notice(f"-{removed} {name} (restam {remaining})")
    removed = 0
    for _ in range(qty):
        if p.pop_aura(name) is not None:
            removed += 1
    for _ in range(qty):
        if p.pop_permanent(name) is not None:
            removed += 1
    return Notice(f"-{removed} {name}")


def use_item_token(state: GameState, side: str, name: str, cards: dict[str, Card]) -> Notice:
    """Ativa item token: paga custo, destroi, compra 1 carta, Go Again."""
    p = state.players[side]
    cost = ITEM_TOKEN_COSTS.get(name)
    if cost is None:
        raise CombatError(f"{name} não é um item token ativável")
    if p.tokens.get(name, 0) <= 0:
        raise CombatError(f"nenhum {name} para ativar")
    if p.pitch_pool < cost:
        raise CombatError(f"custo insuficiente ({p.pitch_pool} < {cost})")
    # Pagar custo e destruir
    p.pitch_pool -= cost
    p.pop_token(name, 1)
    # Comprar 1 carta (será controlado pelo caller via draw manual)
    return Notice(f"{name} ativado: -{cost}{{r}}, compre 1 carta")


# ---------------------------------------------------------------------------
# Vida (ajuste manual)
# ---------------------------------------------------------------------------


def adjust_life(state: GameState, side: str, delta: int) -> Notice:
    """Ajusta a vida do lado indicado; delta negativo tira, positivo soma.

    Uso manual para eventos fora do combate (efeitos especiais, erro de
    trigger, setup). O `resolve` de combat.py já aplica dano automaticamente.
    """
    if side not in state.players:
        raise CombatError(f"lado inválido: {side} (use A ou B)")
    if delta == 0:
        raise CombatError("delta de vida deve ser diferente de zero")
    p = state.players[side]
    p.life += delta
    sinal = "+" if delta > 0 else ""
    return Notice(f"{side}: vida {p.life} ({sinal}{delta})")


def has_aura(player: PlayerState, name: str) -> bool:
    """Verifica se o jogador controla ao menos 1 cópia da aura."""
    return bool(player.auras.get(name))


def count_auras(player: PlayerState, name: str) -> int:
    """Conta cópias da aura."""
    return len(player.auras.get(name, []))


# ---------------------------------------------------------------------------
# Jogando cartas
# ---------------------------------------------------------------------------


def may_play_from_graveyard(state: GameState, side: str) -> bool:
    """Passiva do Gravy Bones: jogar do cemitério se um blue entrou nele no turno."""
    p = state.players[side]
    return p.hero_key in GRAVY_BONES_HEROES and p.blue_to_graveyard_this_turn > 0


def _check_graveyard_play(state: GameState, side: str, card: Card) -> None:
    """Valida a passiva watery grave do Gravy Bones para jogar do cemitério."""
    if not may_play_from_graveyard(state, side):
        raise CombatError(
            "Gravy Bones: exige um card blue no cemitério neste turno para jogar de lá"
        )
    if not card.is_watery_grave:
        raise CombatError(f"{card.name} não tem watery grave")


def play_action(
    state: GameState,
    side: str,
    card_key: str,
    cards: dict[str, Card],
    *,
    go_again_earned: bool | None = None,
    source: str = "hand",
) -> list[Notice]:
    """Joga uma non-attack action da mão ou do cemitério (watery grave).

    go_again_earned: None = deduz das keywords da carta; passe False quando o
    Go Again for condicional e não satisfeito, True quando concedido por outro
    efeito.
    source: "hand" (default) ou "graveyard" (passiva do Gravy Bones).
    """
    notices: list[Notice] = []
    p = state.players[side]
    card = _require(cards, card_key)
    if "Defense Reaction" in card.types:
        raise CombatError("Defense Reaction é jogada durante a defesa")
    if not card.is_non_attack_action:
        raise CombatError(f"{card.name} não é uma non-attack action")
    if source not in ("hand", "graveyard"):
        raise CombatError(f"origem inválida: {source} (use hand ou graveyard)")
    if source == "hand":
        if card_key not in p.hand:
            raise CombatError(f"{card.name} não está na mão")
    else:
        if card_key not in p.graveyard:
            raise CombatError(f"{card.name} não está no cemitério")
        _check_graveyard_play(state, side, card)

    cost = card.cost or 0
    if p.pitch_pool < cost:
        raise CombatError(f"recursos insuficientes ({p.pitch_pool} < {cost})")

    has_go_again = any(kw == "Go again" for kw in card.keywords)
    earned = has_go_again if go_again_earned is None else go_again_earned
    _use_ap(p, earned)

    p.pitch_pool -= cost
    if source == "graveyard":
        p.graveyard.remove(card_key)
        notices.append(Notice(f"{card.name} jogada do cemitério (watery grave)."))
    else:
        _move_card(p.hand, card_key)
    if card.is_permanent:
        p.add_permanent(card_key)
        notices.append(Notice(f"{card.name} fica em jogo (permanente)."))
    p.cards_played_this_turn.append(card_key)
    p.non_attack_actions_played += 1

    # Toda carta jogada vai para a corrente. Jogar uma non-attack action
    # QUEBRA a corrente de combate em andamento: fecha os elos abertos (cartas
    # de ataque/defesa vão aos cemitérios) antes de criar um elo próprio.
    open_link = next((l for l in reversed(state.chain) if not l.resolved), None)
    if open_link is not None:
        notices.extend(
            _close_combat_chain(state, cards, reason="Non-attack action quebrou a corrente")
        )
        link = ChainLink(attacker=side, card_key=card_key, total_damage=0)
        link.played.append(card_key)
        state.chain.append(link)
        notices.append(Notice(f"{card.name} vai para a corrente (novo elo da corrente)."))
    else:
        link = ChainLink(attacker=side, card_key=card_key, total_damage=0)
        link.played.append(card_key)
        state.chain.append(link)
        notices.append(Notice(f"{card.name} vai para a corrente (novo elo da corrente)."))

    # Briar: a 2ª non-attack action do turno cria Embodiment of Lightning.
    if p.hero_key.startswith("Briar") and p.non_attack_actions_played == 2:
        p.add_aura(EMBODIMENT_LIGHTNING)
        notices.append(Notice(f"Briar criou {EMBODIMENT_LIGHTNING} (2ª non-attack action)."))

    # Eloquence: destrói, carta ganha Go Again
    if has_aura(p, TOKEN_ELOQUENCE):
        p.pop_aura(TOKEN_ELOQUENCE)
        earned = True  # força Go Again
        notices.append(Notice(f"{TOKEN_ELOQUENCE} destruído: carta ganhou Go Again."))

    return notices


def play_instant_aura(
    state: GameState,
    side: str,
    card_key: str,
    cards: dict[str, Card],
    *,
    counters_on_enter: int = 0,
) -> Notice:
    """Joga um instant da mão (ex.: Waxing/Waning Vengeance, transcend engine).

    Instants não gastam action points; o custo é pago do pool. A simplificação:
    - cartas com tipo Aura entram em jogo imediatamente (como um token);
    - demais instants (transcend, proteções) vão direto ao cemitério após o
      efeito (não modelado além do lance);
    nada disso cria elo de corrente nem quebra a corrente de combate.

    counters_on_enter: contadores +1{p} condicionais (ex.: Waxing Specter se
    um card blue foi pichado no turno).
    """
    p = state.players[side]
    card = _require(cards, card_key)
    if "Instant" not in card.types:
        raise CombatError(f"{card.name} não é um instant")
    if "Action" in card.types:
        raise CombatError(f"{card.name} é um instant-action; use play_action")
    if card_key not in p.hand:
        raise CombatError(f"{card.name} não está na mão")
    cost = card.cost or 0
    if p.pitch_pool < cost:
        raise CombatError(f"recursos insuficientes ({p.pitch_pool} < {cost})")
    p.pitch_pool -= cost
    _move_card(p.hand, card_key)
    p.cards_played_this_turn.append(card_key)
    if "Aura" not in card.types:
        p.graveyard.append(card_key)
        return Notice(f"{card.name} jogada (instant).")
    p.add_aura(card_key, counters_on_enter)
    if counters_on_enter:
        return Notice(f"{card.name}: aura criada (+{counters_on_enter} contador).")
    return Notice(f"{card.name}: aura criada.")


def play_reaction(
    state: GameState,
    side: str,
    card_key: str,
    cards: dict[str, Card],
) -> list[Notice]:
    """Joga reaction/instant em resposta ao elo aberto.

    Reactions e instants não gastam AP e não quebram a corrente:
    - Defense Reaction: defende o elo do oponente (+defesa, Embodiment of
      Earth incluso); a carta vai ao cemitério do defensor.
    - Attack Reaction: soma o poder ao elo do próprio lado; vai ao cemitério.
    - Instant com tipo Aura: delega a play_instant_aura (aura entra na mesa).
    - Instant genérico: registrado na `responses` do elo e vai ao cemitério
      (efeito não modelado — aplicar manualmente).

    A carta fica listada em `responses` do elo (visível no board/status).
    """
    notices: list[Notice] = []
    p = state.players[side]
    card = _require(cards, card_key)
    is_dr = "Defense Reaction" in card.types
    is_ar = "Attack Reaction" in card.types
    is_instant = "Instant" in card.types
    if not (is_dr or is_ar or is_instant):
        raise CombatError(f"{card.name} não é reaction nem instant")
    if card_key not in p.hand:
        raise CombatError(f"{card.name} não está na mão")

    if is_instant and "Aura" in card.types:
        cost = card.cost or 0
        if p.pitch_pool < cost:
            raise CombatError(f"recursos insuficientes ({p.pitch_pool} < {cost})")
        notice = play_instant_aura(state, side, card_key, cards)
        notices.append(notice)
        link = next((l for l in reversed(state.chain) if not l.resolved), None)
        if link is not None:
            link.responses.append((side, card_key))
        return notices

    cost = card.cost or 0
    if p.pitch_pool < cost:
        raise CombatError(f"recursos insuficientes ({p.pitch_pool} < {cost})")
    p.pitch_pool -= cost
    _move_card(p.hand, card_key)
    p.cards_played_this_turn.append(card_key)
    p.graveyard.append(card_key)

    if is_dr:
        attacker_side = state.opponent_of(side)
        link = current_link(state, attacker_side)
        if link is None:
            raise CombatError("nenhum chain link do oponente para defender")
        defense = card.defense or 0
        if defense == 0:
            notices.append(
                Notice(f"{card.name}: defesa 0 — efeito não modelado, aplicar manualmente.")
            )
        else:
            earth_bonus = bool(p.auras.get(EMBODIMENT_EARTH))
            if earth_bonus and card.is_non_attack_action:
                defense += 1
            link.blocked_by.append(card_key)
            link.blocked_damage += defense
            notices.append(Notice(f"{card.name} defendeu +{defense}."))
        link.responses.append((side, card_key))
        return notices

    if is_ar:
        link = current_link(state, side)
        if link is None:
            raise CombatError("nenhum chain link aberto para o attack reaction")
        power = card.power or 0
        if power:
            link.total_damage += power
            notices.append(Notice(f"{card.name}: ataque +{power}{{p}}."))
        else:
            notices.append(Notice(f"{card.name}: reação sem poder — efeito não modelado."))
        link.responses.append((side, card_key))
        return notices

    link = next((l for l in reversed(state.chain) if not l.resolved), None)
    if link is not None:
        link.responses.append((side, card_key))
    notices.append(Notice(f"{card.name} (instant): efeito não modelado — aplicar manualmente."))
    return notices


def _has_other_illusionist_aura(p: PlayerState, cards: dict[str, Card], self_key: str) -> bool:
    for k in p.auras:
        c = cards.get(k)
        if c is not None and "Illusionist" in c.types and k != self_key:
            return True
    return False


def play_aura_engine(
    state: GameState, side: str, card_key: str, cards: dict[str, Card]
) -> list[Notice]:
    """Joga o motor de auras do Enigma: Spectral Manifestations ou Solitary Companion.

    - Spectral Manifestations: custo 2, Go Again; cria Spectral Shield e, se não
      controla outras auras Illusionist, com +3 contadores (Ward 4).
    - Solitary Companion: custo 0; entra como aura Ward 3 e cria Spectral Shield
      se não controla outras auras Illusionist.
    """
    card = _require(cards, card_key)
    name = card.name
    if name not in ("Spectral Manifestations", "Solitary Companion"):
        raise CombatError(f"{name} não é do motor de auras do Enigma")
    p = state.players[side]
    go_again = name == "Spectral Manifestations"
    notices = play_action(state, side, card_key, cards, go_again_earned=go_again)
    if name == "Spectral Manifestations":
        counters = 3 if not _has_other_illusionist_aura(p, cards, card_key) else 0
        p.add_aura(SPECTRAL_SHIELD, counters)
        if counters:
            notices.append(Notice("Spectral Shield criado com +3 contadores (Ward 4)."))
        else:
            notices.append(Notice("Spectral Shield criado (Ward 1, sem o bônus)."))
    else:
        p.add_aura(card_key, 0)
        if not _has_other_illusionist_aura(p, cards, card_key):
            p.add_aura(SPECTRAL_SHIELD, 0)
            notices.append(Notice("Solitary Companion: Spectral Shield criado (Ward 1)."))
        notices.append(Notice("Solitary Companion: aura Ward 3 criada."))
    return notices


def astral_charge(state: GameState, side: str, cards: dict[str, Card]) -> list[Notice]:
    """Joga Astral Etchings: +3 contadores numa aura com ward.

    Se você controla um Spectral Shield, a carta é jogada como instant (sem
    custo de AP); senão é uma action (gasta 1 AP). O alvo é a aura com ward de
    maior total (a que agrega mais dano/defesa).
    """
    p = state.players[side]
    candidates = [k for k in p.hand if cards.get(k) and "Astral Etchings" in cards[k].name]
    if not candidates:
        raise CombatError("Astral Etchings não está na mão")
    card_key = candidates[0]
    card = _require(cards, card_key)
    cost = card.cost or 0
    if p.pitch_pool < cost:
        raise CombatError(f"recursos insuficientes ({p.pitch_pool} < {cost})")

    targets = [k for k in p.auras if aura_base_ward(cards.get(k)) > 0]
    if not targets:
        raise CombatError("nenhuma aura com ward para receber os contadores")
    target = max(targets, key=lambda k: ward_value(p, k))
    copies = p.auras[target]
    idx = max(range(len(copies)), key=lambda i: copies[i])
    copies[idx] += 3

    if has_aura(p, SPECTRAL_SHIELD):
        # instant: não usa AP
        notices: list[Notice] = [
            Notice("Astral Etchings jogada como instant (controla Spectral Shield).")
        ]
    else:
        _use_ap(p, False)
        notices = [Notice("Astral Etchings jogada (action).")]

    p.pitch_pool -= cost
    _move_card(p.hand, card_key)
    p.cards_played_this_turn.append(card_key)
    link = ChainLink(attacker=side, card_key=card_key, total_damage=0)
    link.played.append(card_key)
    state.chain.append(link)
    notices.append(Notice(f"+3 contadores em {target} (cópia +{copies[idx]})."))
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
    source: str = "hand",
) -> ChainLink:
    """Declara um ataque e cria um chain link.

    - Attack action: paga o custo, sai da mão/arsenal (ou do cemitério, via
      source="graveyard" — passiva watery grave) e consome 1 AP (devolvido
      se ganhar Go Again). Embodiment of Lightning é consumido automaticamente
      para conceder Go Again à próxima attack action.
    - Arma (is_weapon): uma vez por turno; custo em recursos via resource_cost
      (ex.: Star Fall custa 1, ou 0 se Blossom of Spring foi destruída).
      Armas nunca saem do cemitério.
    - power_counters: contadores +1{p} já existentes no atacante.
    """
    p = state.players[side]
    card = _require(cards, card_key)

    if is_weapon:
        if source != "hand":
            raise CombatError("armas não são jogadas do cemitério")
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
        from_graveyard = source == "graveyard"
        from_arsenal = card_key == p.arsenal
        if from_graveyard:
            if card_key not in p.graveyard:
                raise CombatError(f"{card.name} não está no cemitério")
            _check_graveyard_play(state, side, card)
        elif card_key not in p.hand and not from_arsenal:
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
        if from_graveyard:
            p.graveyard.remove(card_key)
        elif from_arsenal:
            p.arsenal = None
        else:
            _move_card(p.hand, card_key)
        p.cards_played_this_turn.append(card_key)
        total = (card.power or 0) + power_counters

    link = ChainLink(attacker=side, card_key=card_key, total_damage=total, dominate=dominate)
    state.chain.append(link)
    if not is_weapon:
        # Arma não é uma carta jogada: permanece equipada (não vai ao cemitério).
        link.played.append(card_key)
    return link


def check_attack_token_triggers(state: GameState, side: str) -> list[Notice]:
    """Verifica tokens que reagem a ataques (Courage, Quicken, Runechant).

    Consome os tokens e retorna lembretes. O caller aplica os efeitos
    usando boost_link / set_arcane_on_link conforme os notices retornados.
    """
    notices: list[Notice] = []
    p = state.players[side]

    # Courage: destrói, ataque +1{p}
    if has_aura(p, TOKEN_COURAGE):
        p.pop_aura(TOKEN_COURAGE)
        notices.append(Notice(f"{TOKEN_COURAGE} destruído: ataque +1{{p}}."))

    # Quicken: destrói, ataque ganha Go Again
    if has_aura(p, TOKEN_QUICKEN):
        p.pop_aura(TOKEN_QUICKEN)
        notices.append(Notice(f"{TOKEN_QUICKEN} destruído: ataque ganhou Go Again."))

    # Runechant: destrói, 1 arcane damage
    if has_aura(p, TOKEN_RUNECHANT):
        p.pop_aura(TOKEN_RUNECHANT)
        notices.append(Notice(f"{TOKEN_RUNECHANT} destruído: 1 arcane damage."))

    return notices


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
        defender.graveyard.append(key)
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


def aura_base_ward(card: Card) -> int:
    """Ward base da carta a partir da keyword (ex.: 'Ward 3' -> 3)."""
    for kw in card.keywords:
        if kw.startswith("Ward"):
            digits = kw.replace("Ward", "").strip()
            if digits.isdigit():
                return int(digits)
    return 0


def activate_hero_ability(state: GameState, side: str, cards: dict[str, Card]) -> Notice:
    """Ativa a habilidade uma vez por turno do Enigma (instant).

    Enigma: 'Once per Turn Instant - 3 recursos: crie um Spectral Shield
    token com um contador +1'. É instant (não gasta AP); consome os recursos
    e marca hero_ability_used.
    """
    p = state.players[side]
    if p.hero_key != "Enigma":
        raise CombatError(f"{p.hero_key} não tem esta habilidade de herói")
    if p.hero_ability_used:
        raise CombatError("habilidade do Enigma já usada neste turno")
    if p.pitch_pool < 3:
        raise CombatError(f"recursos insuficientes ({p.pitch_pool} < 3)")
    p.pitch_pool -= 3
    p.hero_ability_used = True
    p.add_aura(SPECTRAL_SHIELD, 1)
    return Notice("Enigma ativada: Spectral Shield criado com +1 contador.")


def attack_with_aura(
    state: GameState,
    side: str,
    aura_key: str,
    cards: dict[str, Card],
) -> ChainLink:
    """Cosmo ataca usando uma aura com ward que você controla.

    Cosmo, Scroll of Ancestral Tapestry: enquanto Cosmo estiver equipado,
    auras com ward que você controla são armas com poder base = ward e
    'Once per Turn Action - 1 recurso: ataque'. Ataques de aura com contadores
    +1 ganham Go Again.

    - Aura atacada permanece em jogo (não vai à corrente nem ao cemitério).
    - Enigma: o 1º ataque de Spectral Shield no turno custa 1 recurso a menos.
    """
    p = state.players[side]
    if not any("Cosmo" in k for k in p.weapons):
        raise CombatError("Cosmo, Scroll of Ancestral Tapestry não está equipado")
    copies = p.auras.get(aura_key)
    if not copies:
        raise CombatError(f"{aura_key} não está em jogo")
    if aura_key in p.weapon_attacks_this_turn:
        raise CombatError(f"ataque de aura de {aura_key} já usado neste turno")

    card = _require(cards, aura_key)
    base = aura_base_ward(card)
    if base <= 0:
        raise CombatError(f"{card.name} não tem ward (não é arma do Cosmo)")

    best = max(range(len(copies)), key=lambda i: copies[i])
    counters = copies[best]
    total = base + counters

    cost = 1
    if aura_key == SPECTRAL_SHIELD and p.spectral_attacks_this_turn == 0:
        cost = 0
    if p.pitch_pool < cost:
        raise CombatError(f"recursos insuficientes ({p.pitch_pool} < {cost})")
    p.pitch_pool -= cost

    go_again = counters > 0
    _use_ap(p, go_again)

    p.weapon_attacks_this_turn.append(aura_key)
    if aura_key == SPECTRAL_SHIELD:
        p.spectral_attacks_this_turn += 1

    link = ChainLink(attacker=side, card_key=aura_key, total_damage=total)
    state.chain.append(link)
    return link


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

    # Ao resolver, as cartas jogadas neste elo vão ao cemitério do lado atacante
    # (permanentes ficam em jogo; armas nunca entram em `played`).
    moved: list[str] = []
    for key in link.played:
        played_card = cards.get(key)
        if played_card is not None and played_card.is_permanent:
            continue
        state.players[link.attacker].graveyard.append(key)
        moved.append(key)
    if moved:
        notices.append(Notice(f"Cartas do elo foram ao cemitério: {', '.join(moved)}."))
    link.played.clear()

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


def _bump_blue(p: PlayerState, cards: dict[str, Card], card_key: str) -> None:
    """Incrementa blue_to_graveyard_this_turn se a carta é blue.

    Um card blue entrando no cemitério neste turno alimenta a condição da
    passiva watery grave do Gravy Bones (jogar cartas do cemitério).
    """
    card = cards.get(card_key)
    if card is not None and card.color == Color.BLUE:
        p.blue_to_graveyard_this_turn += 1


def _close_combat_chain(
    state: GameState,
    cards: dict[str, Card],
    *,
    reason: str,
) -> list[Notice]:
    """Fecha a corrente de combate movendo as cartas aos cemitérios.

    Jogar uma non-attack action quebra a corrente: as cartas de ataque
    (played) e de defesa da mão (blocked_by) vão ao cemitério dos respectivos
    donos; armas e equipamentos permanecem equipados. Permanentas ficam em
    jogo. Cards blue que entram no cemitério alimentam a passiva watery grave.
    """
    notices: list[Notice] = []
    for link in state.chain:
        if link.resolved:
            continue
        attacker = state.players[link.attacker]
        defender = state.players[state.opponent_of(link.attacker)]

        moved: list[str] = []
        for key in link.played:
            played_card = cards.get(key)
            if played_card is not None and played_card.is_permanent:
                continue
            if key not in attacker.graveyard:
                attacker.graveyard.append(key)
            _bump_blue(attacker, cards, key)
            moved.append(key)
        if moved:
            notices.append(Notice(f"{reason}: cartas de ataque ao cemitério: {', '.join(moved)}."))

        moved_def: list[str] = []
        for key in link.blocked_by:
            block_card = cards.get(key)
            if block_card is not None and block_card.is_equipment:
                continue  # equipamento permanece equipado
            if key not in defender.graveyard:
                defender.graveyard.append(key)
            _bump_blue(defender, cards, key)
            moved_def.append(key)
        if moved_def:
            notices.append(
                Notice(f"{reason}: cartas de defesa ao cemitério: {', '.join(moved_def)}.")
            )

        link.resolved = True
        link.played.clear()
    return notices
