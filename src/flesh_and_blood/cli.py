"""Ponto de entrada da CLI: escolhe os decks e inicia a TUI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from flesh_and_blood.app import Matchup, launch
from flesh_and_blood.carddb import load_cards
from flesh_and_blood.deck import hero_from_deck, load_decklist, validate, weapon_from_deck
from flesh_and_blood.models import new_game
from flesh_and_blood.setup import apply_setup, auto_setup, load_setup_file, setup_weapons

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
    parser.add_argument(
        "--setup",
        type=Path,
        default=None,
        help=(
            "arquivo JSON/YAML com o estado inicial (mãos, arsenal, equipamentos, "
            "armas, pitch_pool) para ambos os jogadores"
        ),
    )
    parser.add_argument(
        "--auto-setup",
        action="store_true",
        help=(
            "prepara a mesa automaticamente antes do turno 1: mão inicial de 4 "
            "cartas do pool (sorteio aleatório) e equipamentos da arena para "
            "ambos os jogadores"
        ),
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help=(
            "semente do sorteio da mão inicial do --auto-setup; use a mesma "
            "semente para reproduzir a mesma mão"
        ),
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
            print(f"aviso ({path}):", file=sys.stderr)
            for e in errors:
                print(f"  - {e}", file=sys.stderr)
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

    # Setup inicial: auto (decklists) e/ou arquivo explícito
    if args.auto_setup:
        auto_setup(state, decks[0], decks[1], cards, seed=args.seed)
        if args.seed is not None:
            print(f"Setup automático aplicado (seed={args.seed}).")
        else:
            print("Setup automático aplicado (mãos sorteadas aleatoriamente).")

    if args.setup is not None:
        try:
            setup = load_setup_file(args.setup)
        except (OSError, ValueError, TypeError, yaml.YAMLError) as e:
            print(f"erro ao ler setup: {e}", file=sys.stderr)
            return 1
        try:
            apply_setup(state, setup, cards)
        except (ValueError, TypeError) as e:
            print(f"setup inválido: {e}", file=sys.stderr)
            return 1
        # Armas do setup sobrescrevem as do deck
        weapons = setup_weapons(setup)
        if weapons.get("A") or weapons.get("B"):
            matchup = Matchup(
                hero_a=matchup.hero_a,
                hero_b=matchup.hero_b,
                weapon_a=weapons.get("A") or matchup.weapon_a,
                weapon_b=weapons.get("B") or matchup.weapon_b,
            )
        print(f"Setup aplicado de: {args.setup}")

    launch(state, cards, matchup=matchup)
    return 0


if __name__ == "__main__":
    sys.exit(main())
