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
from .models import Card

# Tipos/classes permitidos por herói (subset check do formato).
# Briar tem essência de Earth e Lightning (sem Ice); Enigma é Mystic Illusionist.
HERO_ALLOWED_TYPES: dict[str, frozenset[str]] = {
    "Briar, Warden of Thorns": frozenset(
        {"Generic", "Elemental", "Runeblade", "Earth", "Lightning", "Hero"}
    ),
    "Enigma": frozenset({"Generic", "Illusionist", "Mystic", "Hero"}),
}

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

    allowed = HERO_ALLOWED_TYPES.get(deck.hero)

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
