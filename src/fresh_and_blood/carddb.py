"""Carregamento do registro de cartas (data/cards.yaml)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from .models import Card, Color

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
CARDS_FILE = DATA_DIR / "cards.yaml"


def load_cards(path: Path = CARDS_FILE) -> dict[str, Card]:
    """Carrega registro de cartas com cache por arquivo.

    Evita reler o YAML a cada chamada (importante com 4950+ cartas).
    """
    return _load_cached(str(path))


@lru_cache(maxsize=4)
def _load_cached(path_str: str) -> dict[str, Card]:
    path = Path(path_str)
    with open(path, encoding="utf-8") as f:
        raw: dict[str, dict] = yaml.safe_load(f)
    return {key: _parse(key, entry) for key, entry in raw.items()}


def _parse(key: str, entry: dict) -> Card:
    color = entry.get("color")
    return Card(
        key=key,
        name=entry["name"],
        color=Color(color) if color else None,
        pitch=entry.get("pitch"),
        cost=entry.get("cost"),
        power=entry.get("power"),
        defense=entry.get("defense"),
        types=tuple(entry.get("types", ())),
        keywords=tuple(entry.get("keywords", ())),
        text=entry.get("text", ""),
        rarity=entry.get("rarity", ""),
        sa_legal=bool(entry.get("sa_legal", False)),
    )
