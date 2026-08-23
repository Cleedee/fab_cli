"""Decklists: carga e validação das regras de construção do Silver Age.

Regras do formato (TRP 7.4):
- 1 herói jovem + pool de 55 cartas (armas + equipamentos + deck)
- exatamente 40 cartas apresentadas no início da partida
- até 2 cópias por carta única (nome + cor)
- apenas raridades common, rare e basic
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from .carddb import load_cards
from .models import Card, Hero

# Tipos/classes permitidos por herói (subset check do formato).
# Overrides manuais para capturar talents/essências que o dataset não modela
# (ex.: Briar tem essência de Earth e Lightning nos keywords, não nos types).
# Heróis fora deste mapa usam fallback automático dos types do card do herói.
HERO_ALLOWED_TYPES: dict[str, frozenset[str]] = {
    "Briar, Warden of Thorns": frozenset(
        {"Generic", "Elemental", "Runeblade", "Earth", "Lightning", "Hero"}
    ),
    "Enigma": frozenset({"Generic", "Illusionist", "Mystic", "Hero"}),
}

# Tipos do card de herói que NÃO são classes/talents jogáveis por cartas de deck.
_HERO_NON_CARD_TYPES = frozenset({"Hero", "Young", "Token"})

# Jovens do formato Silver Age: 20 vida / 4 intelecto (TRP 7.4).
DEFAULT_YOUNG_LIFE = 20
DEFAULT_YOUNG_INTELLECT = 4


def allowed_types_for(hero_key: str, cards: dict[str, Card] | None = None) -> frozenset[str] | None:
    """Tipos de carta permitidos para o herói.

    Usa o override manual quando existe; senão deriva dos types do card do
    herói no registro (ex.: {'Elemental', 'Runeblade'}), adicionando 'Generic'.
    Retorna None se o herói não está no registro.
    """
    if hero_key in HERO_ALLOWED_TYPES:
        return HERO_ALLOWED_TYPES[hero_key]
    cards = cards if cards is not None else load_cards()
    hero = cards.get(hero_key)
    if hero is None:
        return None
    return frozenset({"Generic", *hero.types}) - _HERO_NON_CARD_TYPES


MAX_POOL_SIZE = 55
MAX_COPIES = 2


@dataclass
class Decklist:
    hero: str
    source: str
    arena: list[str]
    deck_pool: dict[str, int]  # chave -> quantidade
    path: Path | None = None

    @property
    def pool_size(self) -> int:
        return len(self.arena) + sum(self.deck_pool.values())

    def all_keys(self) -> set[str]:
        return set(self.arena) | set(self.deck_pool)


def load_decklist(path: str | Path) -> Decklist:
    path = Path(path)
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return Decklist(
        hero=raw["hero"],
        source=raw.get("source", ""),
        arena=list(raw.get("arena", [])),
        deck_pool={e["card"]: int(e["qty"]) for e in raw["deck_pool"]},
        path=path,
    )


def validate(deck: Decklist, cards: dict[str, Card] | None = None) -> list[str]:
    """Retorna lista de problemas (vazia = deck válido para Silver Age)."""
    cards = cards if cards is not None else load_cards()
    errors: list[str] = []

    hero = cards.get(deck.hero)
    if hero is None:
        errors.append(f"herói desconhecido: {deck.hero}")
    elif "Hero" not in hero.types or "Young" not in hero.types:
        errors.append(f"{deck.hero} não é um herói jovem")

    allowed = allowed_types_for(deck.hero, cards)

    for key in sorted(deck.all_keys()):
        card = cards.get(key)
        if card is None:
            errors.append(f"carta não encontrada no registro: {key}")
            continue
        if not card.sa_legal:
            errors.append(f"ilegal em Silver Age: {key}")
        # toda carta deve compartilhar ao menos um tipo/classe com o herói
        allowed_types = (allowed - {"Hero"}) if allowed is not None else None
        if allowed_types is not None and not set(card.types) & allowed_types:
            errors.append(f"{key}: tipos {card.types} fora do card-pool do herói")
        if any(t in card.types for t in ("Ice",)):
            errors.append(f"{key}: supertipo Ice proibido para este herói")

    for key, qty in deck.deck_pool.items():
        if qty > MAX_COPIES:
            errors.append(f"{key}: {qty} cópias (máximo {MAX_COPIES})")

    if deck.pool_size != MAX_POOL_SIZE:
        errors.append(f"pool tem {deck.pool_size} cartas (deve ter {MAX_POOL_SIZE})")

    return errors


def hero_from_deck(deck: Decklist, cards: dict[str, Card] | None = None) -> Hero:
    """Deriva o objeto Hero de uma decklist a partir do registro de cartas.

    Vida/intelecto usam o padrão de jovem do Silver Age (20/4); classes e
    talents vêm dos types do card do herói (ex.: Runeblade, Illusionist).
    """
    cards = cards if cards is not None else load_cards()
    card = cards.get(deck.hero)
    if card is None:
        raise ValueError(f"herói desconhecido: {deck.hero}")
    classes = tuple(t for t in card.types if t not in _HERO_NON_CARD_TYPES and t != "Generic")
    return Hero(
        key=card.key,
        name=card.name,
        life=DEFAULT_YOUNG_LIFE,
        intellect=DEFAULT_YOUNG_INTELLECT,
        classes=classes,
        talents=(),
    )


def weapon_from_deck(deck: Decklist, cards: dict[str, Card] | None = None) -> str | None:
    """Primeira arma da arena da decklist (chave da carta)."""
    cards = cards if cards is not None else load_cards()
    for key in deck.arena:
        card = cards.get(key)
        if card is not None and card.is_weapon:
            return key
    return None
