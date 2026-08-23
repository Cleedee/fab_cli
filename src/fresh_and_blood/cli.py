"""CLI mínima — placeholder até a Fase 1."""

from __future__ import annotations

import sys

from fresh_and_blood.app import launch
from fresh_and_blood.carddb import load_cards
from fresh_and_blood.models import Hero, new_game

BRIAR = Hero(
    key="Briar, Warden of Thorns",
    name="Briar, Warden of Thorns",
    life=20,
    intellect=4,
    classes=("Runeblade",),
    talents=("Earth", "Lightning"),
)
ENIGMA = Hero(
    key="Enigma",
    name="Enigma",
    life=20,
    intellect=4,
    classes=("Illusionist",),
    talents=("Mystic",),
)


def main() -> int:
    cards = load_cards()
    state = new_game(BRIAR, ENIGMA, "A")
    launch(state, cards)
    return 0


if __name__ == "__main__":
    sys.exit(main())
