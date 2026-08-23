"""Setup inicial de partida: mãos, equipamentos, arsenal e armas antes do turno 1.

Permite iniciar uma partida já com as cartas na mão e equipamentos na arena,
sem digitar os comandos draw/equip manualmente. Usado pela CLI (--setup e
--auto-setup) antes de lançar a TUI.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import yaml

from .deck import Decklist
from .models import Card, GameState

VALID_SIDES = ("A", "B")


def load_setup_file(path: str | Path) -> dict:
    """Carrega um arquivo de setup (JSON ou YAML)."""
    path = Path(path)
    with open(path, encoding="utf-8") as f:
        if path.suffix.lower() in (".yaml", ".yml"):
            data = yaml.safe_load(f)
        else:
            data = json.load(f)
    if not isinstance(data, dict):
        raise TypeError("setup deve ser um objeto (dict) no topo.")
    return data


def _validate_key(key: str, cards: dict[str, Card], *, want_equipment: bool = False) -> None:
    """Valida que a carta existe no registro (e é equipamento quando exigido)."""
    card = cards.get(key)
    if card is None:
        raise ValueError(f"carta desconhecida no setup: {key}")
    if want_equipment and not card.is_equipment:
        raise ValueError(f"{key} não é um equipamento")


def apply_setup(state: GameState, setup: dict, cards: dict[str, Card]) -> None:
    """Aplica um setup inicial ao GameState.

    Formato esperado (todas as chaves opcionais):
        {
          "hands":     {"A": ["Snatch (red)", ...], "B": [...]},
          "arsenal":   {"A": "Snatch (red)", "B": null},
          "equipment": {"A": ["Blade Beckoner Helm", ...], "B": [...]},
          "weapons":   {"A": "Star Fall", "B": null},   # não muda o state; usado pelo caller
          "pitch_pool": {"A": 0, "B": 0}
        }
    """
    # Mãos
    for side, hand in setup.get("hands", {}).items():
        if side not in VALID_SIDES:
            raise ValueError(f"lado inválido no setup: {side}")
        for key in hand:
            _validate_key(key, cards)
            state.players[side].hand.append(key)

    # Arsenal
    for side, key in setup.get("arsenal", {}).items():
        if side not in VALID_SIDES:
            raise ValueError(f"lado inválido no setup: {side}")
        if key:
            _validate_key(key, cards)
            state.players[side].arsenal = key

    # Equipamentos na arena
    for side, eqs in setup.get("equipment", {}).items():
        if side not in VALID_SIDES:
            raise ValueError(f"lado inválido no setup: {side}")
        for key in eqs:
            _validate_key(key, cards, want_equipment=True)
            state.players[side].equipment_uses[key] = None

    # Pool de recursos inicial
    for side, pool in setup.get("pitch_pool", {}).items():
        if side not in VALID_SIDES:
            raise ValueError(f"lado inválido no setup: {side}")
        if pool < 0:
            raise ValueError(f"pitch_pool negativo para {side}: {pool}")
        state.players[side].pitch_pool = int(pool)


def setup_weapons(setup: dict) -> dict[str, str | None]:
    """Retorna as armas definidas no setup (por lado), se houver."""
    return {side: setup.get("weapons", {}).get(side) for side in VALID_SIDES}


def auto_setup(
    state: GameState,
    deck_a: Decklist,
    deck_b: Decklist,
    cards: dict[str, Card],
    *,
    hand_size: int = 4,
    seed: int | None = None,
) -> None:
    """Pré-prepara o estado usando as decklists: mão inicial e equipamentos da arena.

    - Mão: `hand_size` cartas do pool do deck. Com `seed=None`, embaralha o
      pool (mão aleatória a cada execução). Com `seed`, a mesma semente
      reproduz exatamente a mesma mão (útil para reproduzir partidas).
    - Equipamentos: todos os equipamentos listados em `arena`.
    - Arsenal: vazio (o usuário decide).
    - Arma: derivada do deck pelo caller (weapon_from_deck), não muda o state.

    A mão é sorteada do pool EXPANDIDO por quantidade (ex.: 2 cópias de Snatch
    entram 2x no sorteio), refletindo o baralho físico.
    """
    rng = random.Random(seed)
    for side, deck in (("A", deck_a), ("B", deck_b)):
        p = state.players[side]
        # Equipamentos da arena
        for key in deck.arena:
            card = cards.get(key)
            if card is not None and card.is_equipment:
                p.equipment_uses[key] = None
        # Mão inicial: embaralha o pool expandido (por quantidade) e pega as primeiras
        pool_expanded = [key for key, qty in deck.deck_pool.items() for _ in range(qty)]
        rng.shuffle(pool_expanded)
        p.hand.extend(pool_expanded[:hand_size])
