#!/usr/bin/env python3
"""Gera data/cards.yaml a partir do dataset the-fab-cube/flesh-and-blood-cards.

Uso:
    python scripts/build_cards.py \
        --dataset-dir /caminho/fab-json/json/english \
        --decks-dir data/decks \
        --out data/cards.yaml

O dataset pode ser baixado de:
    https://github.com/the-fab-cube/flesh-and-blood-cards/releases
(arquivo json.zip da release mais recente)

O registro gerado contém somente as cartas usadas nos decks em --decks-dir,
mais os tokens relevantes. Campos numéricos vazios viram null.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

TOKENS = ["Spectral Shield", "Embodiment of Earth", "Embodiment of Lightning"]
COLOR_SUFFIX = re.compile(r"\s*\((red|yellow|blue)\)$", re.IGNORECASE)
COLORS = {"Red": "red", "Yellow": "yellow", "Blue": "blue"}

RARITY_RANK = {"T": 0, "C": 1, "R": 2, "M": 3, "L": 4, "S": 5, "F": 6, "V": 7}

# Correções manuais para limitações conhecidas do dataset.
# Briar jovem é dupla-face com a adulta (ELE062//ELE063): o dataset funde as duas
# num objeto só, perdendo o subtipo "Young" e marcando silver_age_legal=False
# (a face adulta é que é ilegal). A face jovem é legal em Silver Age.
OVERRIDES: dict[str, dict] = {
    "Briar, Warden of Thorns": {
        "types_append": ["Young"],
        "sa_legal_force": True,
    },
}


def apply_overrides(name: str, entry: dict) -> dict:
    override = OVERRIDES.get(name)
    if not override:
        return entry
    entry = {**entry}
    if "types_append" in override:
        entry["types"] = entry["types"] + [
            t for t in override["types_append"] if t not in entry["types"]
        ]
    if "sa_legal_force" in override:
        entry["sa_legal"] = override["sa_legal_force"]
    return entry


def norm(name: str) -> str:
    return re.sub(r"\s+", " ", name.replace("||", "//")).strip().lower()


def parse_key(key: str) -> tuple[str, str | None]:
    m = COLOR_SUFFIX.search(key)
    if m:
        return key[: m.start()].strip(), m.group(1).lower()
    return key.strip(), None


def collect_required_keys(decks_dir: Path) -> tuple[set[str], set[str]]:
    """Retorna (chaves_de_cartas, nomes_sem_cor_incluindo_herois)."""
    keys: set[str] = set()
    plain_names: set[str] = set(TOKENS)
    for path in sorted(decks_dir.glob("*.yaml")):
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        plain_names.add(raw["hero"])
        for item in raw.get("arena", []):
            base, color = parse_key(item)
            if color:
                keys.add(item)
            else:
                plain_names.add(base)
        for entry in raw["deck_pool"]:
            base, color = parse_key(entry["card"])
            if color:
                keys.add(entry["card"])
            else:
                plain_names.add(base)
    return keys, plain_names


def best_rarity(card: dict) -> str:
    rarities = [p.get("rarity", "") for p in card.get("printings", [])]
    if not rarities:
        return ""
    return min(rarities, key=lambda r: RARITY_RANK.get(r, 99))


def to_entry(card: dict) -> dict:
    def num(value: str) -> int | None:
        return int(value) if str(value).strip().isdigit() else None

    keywords = [
        kw.strip()
        for chunk in card.get("card_keywords", [])
        if chunk
        for kw in chunk.split(",")
        if kw.strip()
    ]
    return {
        "name": card["name"],
        "color": COLORS.get(card.get("color", "")),
        "pitch": num(card.get("pitch", "")),
        "cost": num(card.get("cost", "")),
        "power": num(card.get("power", "")),
        "defense": num(card.get("defense", "")),
        "types": card.get("types", []),
        "keywords": keywords,
        "text": card.get("functional_text_plain", ""),
        "rarity": best_rarity(card),
        "sa_legal": bool(card.get("silver_age_legal")) and not card.get("silver_age_banned"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", required=True, type=Path)
    parser.add_argument("--decks-dir", type=Path, default=Path("data/decks"))
    parser.add_argument("--out", type=Path, default=Path("data/cards.yaml"))
    args = parser.parse_args()

    with open(args.dataset_dir / "card.json", encoding="utf-8") as f:
        all_cards = json.load(f)

    index_by_name_color: dict[tuple[str, str | None], dict] = {}
    index_by_name: dict[str, list[dict]] = {}
    for card in all_cards:
        color = COLORS.get(card.get("color", ""))
        index_by_name_color[(norm(card["name"]), color)] = card
        index_by_name.setdefault(norm(card["name"]), []).append(card)

    colored_keys, plain_names = collect_required_keys(args.decks_dir)

    out: dict[str, dict] = {}
    missing: list[str] = []

    for key in sorted(colored_keys):
        base, color = parse_key(key)
        card = index_by_name_color.get((norm(base), color))
        if card is None:
            missing.append(key)
        else:
            out[key] = apply_overrides(key, to_entry(card))

    for name in sorted(plain_names):
        candidates = index_by_name.get(norm(name), [])
        if not candidates:
            missing.append(name)
            continue
        # sem cor: se houver várias impressões coloridas, usa a primeira (tokens/herois não têm)
        card = candidates[0]
        entry = apply_overrides(name, to_entry(card))
        if entry["color"] is not None and len(candidates) > 1:
            print(
                f"Aviso: '{name}' tem versões coloridas; usando a primeira "
                f"({entry['color']}). Prefira chaves com sufixo de cor.",
                file=sys.stderr,
            )
        out[name] = entry

    if missing:
        print("Cartas não encontradas no dataset:", file=sys.stderr)
        for name in missing:
            print(f"  - {name}", file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "# GERADO POR scripts/build_cards.py — não editar à mão.\n"
        "# Fonte: the-fab-cube/flesh-and-blood-cards\n\n"
    )
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(header)
        yaml.safe_dump(out, f, allow_unicode=True, sort_keys=True, width=100)

    print(f"{len(out)} cartas escritas em {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
