"""Ponto de entrada da CLI: escolhe os decks e inicia a TUI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from fresh_and_blood.app import Matchup, launch
from fresh_and_blood.carddb import load_cards
from fresh_and_blood.deck import hero_from_deck, load_decklist, validate, weapon_from_deck
from fresh_and_blood.models import new_game

DECK_DIR = Path(__file__).resolve().parents[2] / "data" / "decks"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fab",
        description="Assistente de decisão para FaB Silver Age (Briar vs Enigma por padrão).",
    )
    parser.add_argument(
        "--deck-a",
        type=Path,
        default=DECK_DIR / "briar_sa.yaml",
        help="decklist YAML do jogador A (padrão: Briar)",
    )
    parser.add_argument(
        "--deck-b",
        type=Path,
        default=DECK_DIR / "enigma_sa.yaml",
        help="decklist YAML do jogador B (padrão: Enigma)",
    )
    parser.add_argument(
        "--first",
        choices=("A", "B"),
        default="A",
        help="quem começa (padrão: A)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cards = load_cards()

    # Carrega e valida as decklists
    decks = []
    for side, path in (("A", args.deck_a), ("B", args.deck_b)):
        try:
            deck = load_decklist(path)
        except FileNotFoundError:
            print(f"erro: decklist não encontrada: {path}", file=sys.stderr)
            return 1
        errors = validate(deck, cards)
        if errors:
            print(f"decklist inválida ({path}):", file=sys.stderr)
            for e in errors:
                print(f"  - {e}", file=sys.stderr)
            return 1
        decks.append(deck)

    # Deriva heróis e armas das decklists
    hero_a, hero_b = (hero_from_deck(d, cards) for d in decks)
    matchup = Matchup(
        hero_a=hero_a,
        hero_b=hero_b,
        weapon_a=weapon_from_deck(decks[0], cards),
        weapon_b=weapon_from_deck(decks[1], cards),
    )

    state = new_game(hero_a, hero_b, args.first)
    launch(state, cards, matchup=matchup)
    return 0


if __name__ == "__main__":
    sys.exit(main())
