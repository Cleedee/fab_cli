"""Modelos de dados: cartas, heróis e estado de partida.

Fase 0 — o estado é mantido manualmente pelo usuário; os modelos existem
para garantir consistência e permitir save/load.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Color(str, Enum):
    RED = "red"
    YELLOW = "yellow"
    BLUE = "blue"


@dataclass(frozen=True)
class Card:
    """Uma carta única (nome + cor)."""

    key: str  # identificador único, ex.: "Ravenous Rabble (red)"
    name: str
    color: Color | None  # None para cartas sem cor (equipamento etc.)
    pitch: int | None
    cost: int | None
    power: int | None
    defense: int | None
    types: tuple[str, ...]
    keywords: tuple[str, ...]
    text: str
    rarity: str
    sa_legal: bool

    @property
    def is_attack(self) -> bool:
        return "Attack" in self.types and "Action" in self.types

    @property
    def is_non_attack_action(self) -> bool:
        return "Action" in self.types and "Attack" not in self.types

    @property
    def is_weapon(self) -> bool:
        return "Weapon" in self.types

    @property
    def is_offhand(self) -> bool:
        """Equipamento que ocupa o segundo slot de arma (ex.: escudos, grimórios)."""
        return "Off-Hand" in self.types

    @property
    def is_equipment(self) -> bool:
        return "Equipment" in self.types

    @property
    def is_ally(self) -> bool:
        return "Ally" in self.types

    @property
    def is_item(self) -> bool:
        return "Item" in self.types

    @property
    def is_permanent(self) -> bool:
        """Permanente: fica em jogo (arena) depois de jogada (Ally/Item/Landmark)."""
        return "Ally" in self.types or "Item" in self.types or "Landmark" in self.types

    @property
    def equipment_slot(self) -> str | None:
        """Slot do equipamento: Head, Chest, Arms, Legs ou Off-Hand. None se não tem slot."""
        for slot in ("Head", "Chest", "Arms", "Legs"):
            if slot in self.types:
                return slot
        if "Off-Hand" in self.types:
            return "Off-Hand"
        return None

    @property
    def is_hero(self) -> bool:
        return "Hero" in self.types

    @property
    def is_watery_grave(self) -> bool:
        """Carta com a mecânica watery grave (presente no texto da carta)."""
        return "watery grave" in self.text.lower()


@dataclass(frozen=True)
class Hero:
    """Carta de herói (estática durante a partida)."""

    key: str
    name: str
    life: int
    intellect: int
    classes: tuple[str, ...]
    talents: tuple[str, ...]


@dataclass
class PlayerState:
    """Estado dinâmico de um dos lados da mesa."""

    hero_key: str
    life: int = 20
    hand: list[str] = field(default_factory=list)
    arsenal: str | None = None
    graveyard: list[str] = field(default_factory=list)
    banished: list[str] = field(default_factory=list)
    pitch_pool: int = 0  # recursos flutuantes
    action_points: int = 1
    # auras em jogo: chave da carta -> lista de contadores +1 por cópia
    auras: dict[str, list[int]] = field(default_factory=dict)
    # permanentes em jogo (Ally/Item/Landmark): chave -> contadores por cópia
    permanents: dict[str, list[int]] = field(default_factory=dict)
    # equipamentos usáveis: chave -> durabilidade restante (None = destrói-se só por efeito)
    equipment_uses: dict[str, int | None] = field(default_factory=dict)
    equipment_destroyed: list[str] = field(default_factory=list)
    # armas em jogo: 0-2 cartas. Arma 2H ocupa slot único (fora o limite de 2).
    weapons: list[str] = field(default_factory=list)
    # Off-Hand: equipamento que ocupa o segundo slot de arma (ex.: escudo).
    # Só pode haver um; não pode coexistir com arma 2H.
    offhand_key: str | None = None
    # tokens item: nome -> quantidade (Gold, Silver, Copper, etc.)
    tokens: dict[str, int] = field(default_factory=dict)

    # --- contadores por turno (resetados em start_turn) ---
    hero_ability_used: bool = False
    equipment_used_this_turn: list[str] = field(default_factory=list)
    non_attack_actions_played: int = 0
    weapon_attacks_this_turn: list[str] = field(default_factory=list)
    first_attack_damage_done: bool = False
    cards_played_this_turn: list[str] = field(default_factory=list)
    # Gravy Bones: um card blue entrando no cemitério neste turno habilita
    # jogar cartas com watery grave de lá (resetado em start_turn).
    blue_to_graveyard_this_turn: int = 0

    def damage(self, amount: int) -> int:
        self.life -= amount
        return amount

    def heal(self, amount: int) -> None:
        self.life += amount

    def add_aura(self, card_key: str, counters: int = 0) -> int:
        """Cria uma cópia da aura; retorna o índice dela."""
        self.auras.setdefault(card_key, []).append(counters)
        return len(self.auras[card_key]) - 1

    def pop_aura(self, card_key: str, index: int | None = None) -> int | None:
        """Destrói uma cópia da aura; retorna os contadores dela (ou None se não há)."""
        copies = self.auras.get(card_key)
        if not copies:
            return None
        if index is None:
            index = len(copies) - 1
        counters = copies.pop(index)
        if not copies:
            del self.auras[card_key]
        return counters

    def add_permanent(self, card_key: str, counters: int = 0) -> int:
        """Coloca uma permanente em jogo; retorna o índice da cópia."""
        self.permanents.setdefault(card_key, []).append(counters)
        return len(self.permanents[card_key]) - 1

    def pop_permanent(self, card_key: str, index: int | None = None) -> int | None:
        """Remove uma cópia da permanente (destruída); retorna os contadores dela (ou None)."""
        copies = self.permanents.get(card_key)
        if not copies:
            return None
        if index is None:
            index = len(copies) - 1
        counters = copies.pop(index)
        if not copies:
            del self.permanents[card_key]
        return counters

    def add_token(self, name: str, qty: int = 1) -> int:
        """Cria tokens item; retorna a quantidade total."""
        self.tokens[name] = self.tokens.get(name, 0) + qty
        return self.tokens[name]

    def pop_token(self, name: str, qty: int = 1) -> int:
        """Remove tokens item; retorna a quantidade restante (0 se nenhum)."""
        current = self.tokens.get(name, 0)
        remove = min(qty, current)
        new = current - remove
        if new > 0:
            self.tokens[name] = new
        else:
            self.tokens.pop(name, None)
        return new


@dataclass
class ChainLink:
    """Um link da cadeia de combate."""

    attacker: str  # lado atacante ("A" ou "B")
    card_key: str
    total_damage: int  # poder base + boosts acumulados
    blocked_by: list[str] = field(default_factory=list)  # chaves das cartas defensoras
    blocked_damage: int = 0
    arcane_damage: int = 0  # componente arcano pendente (não é bloqueado por cartas)
    # Dominate restringe QUANTAS cartas podem defender (validação na fase de defesa),
    # não altera a matemática do dano.
    dominate: bool = False
    resolved: bool = False

    @property
    def damage_remaining(self) -> int:
        return max(0, self.total_damage - self.blocked_damage)


@dataclass
class GameState:
    """Estado completo da partida."""

    players: dict[str, PlayerState]  # "A" e "B"
    active_player: str = "A"
    turn: int = 1
    chain: list[ChainLink] = field(default_factory=list)

    def opponent_of(self, side: str) -> str:
        return "B" if side == "A" else "A"

    def to_dict(self) -> dict[str, Any]:
        from dataclasses import asdict

        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GameState:
        chain = [ChainLink(**link) for link in data["chain"]]
        players = {side: PlayerState(**pstate) for side, pstate in data["players"].items()}
        state = cls(players=players, turn=data["turn"], active_player=data["active_player"])
        state.chain = chain
        return state


def new_game(hero_a: Hero, hero_b: Hero, first_player: str = "A") -> GameState:
    """Cria o estado inicial com base nas cartas de herói escolhidas."""

    def make(side: str, hero: Hero) -> PlayerState:
        return PlayerState(
            hero_key=hero.key,
            life=hero.life,
            hand=[],
            equipment_uses={},
            action_points=1 if side == first_player else 0,
        )

    return GameState(
        players={"A": make("A", hero_a), "B": make("B", hero_b)},
        active_player=first_player,
    )


def draw(state: GameState, side: str, card_key: str) -> None:
    """Compra manual (o usuário diz qual carta entrou na mão)."""
    state.players[side].hand.append(card_key)


def pitch_card(card: Card) -> int:
    """Recursos gerados ao dar pitch numa carta."""
    if card.pitch is None:
        raise ValueError(f"{card.key} não tem valor de pitch")
    return card.pitch


def pay_cost(player: PlayerState, cost: int) -> None:
    if player.pitch_pool < cost:
        raise ValueError(f"recursos insuficientes: {player.pitch_pool} < {cost}")
    player.pitch_pool -= cost
