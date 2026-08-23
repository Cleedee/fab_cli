#!/usr/bin/env python3
"""Baixa uma decklist da fabtcg.com e converte para o formato YAML do projeto.

Uso:
    python scripts/fetch_decklist.py <url> [--out data/decks/<nome>.yaml]

A URL deve ser uma página individual de decklist (ex.:
https://fabtcg.com/decklists/richard-gillingham-enigma-...).

O formato de saída é compatível com fab --deck-a data/decks/<nome>.yaml.

Também aceita arquivos HTML locais (útil para debug):
    python scripts/fetch_decklist.py /caminho/para/pagina.html

Dependências: PyYAML, requests (se for baixar da internet).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import requests

OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "decks"

# Mapa de cores: como aparecem no HTML (fabtcg.com) -> nome canônico
COLOR_MAP: dict[str, str] = {
    "red": "red",
    "yel": "yellow",
    "blu": "blue",
    "yellow": "yellow",
    "blue": "blue",
}

CARD_ITEM_RE = re.compile(
    r'<div\s+class="card-name"[^>]*>\s*<span>\s*(\d+)x\s*</span>\s*(.+?)\s*</div>',
    re.IGNORECASE | re.DOTALL,
)

COLOR_SUFFIX_RE = re.compile(r"\s*\((red|yellow|blue|yel|blu)\)$", re.IGNORECASE)


def parse_card_line(name_raw: str) -> tuple[str, int | None]:
    """Extrai (chave_da_carta, quantidade) de um nome extraído do HTML.

    Exemplos de entrada:
      'Snatch (red)'        -> 'Snatch (red)', None
      '1x Snatch (red)'     -> 'Snatch (red)', 1
      'Cosmo, Scroll of...' -> 'Cosmo, Scroll of...', None
      'Fyendal&#039;s...'   -> "Fyendal's...", None  (decodifica entidades)
    """
    # Decodifica entidades HTML básicas
    name_raw = (
        name_raw.replace("&#039;", "'")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
    )
    name_raw = name_raw.strip()

    # Normaliza cor
    m = COLOR_SUFFIX_RE.search(name_raw)
    if m:
        raw_color = m.group(1).lower()
        canon = COLOR_MAP.get(raw_color)
        if canon and canon != raw_color:
            name_raw = name_raw[: m.start(1)] + canon + name_raw[m.end(1) :]

    return name_raw, None


def _decode_html_entities(text: str) -> str:
    """Decodifica entidades HTML básicas (apóstrofos, &, <, >, aspas)."""
    return (
        text.replace("&#039;", "'")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
    )


def _normalize_color(name: str) -> str:
    """Converte sufixo de cor do HTML ((yel)/(blu)) para canônico ((yellow)/(blue))."""
    m = COLOR_SUFFIX_RE.search(name)
    if m:
        raw = m.group(1).lower()
        canon = COLOR_MAP.get(raw)
        if canon and canon != raw:
            return name[: m.start(1)] + canon + name[m.end(1) :]
    return name


def _split_cards_by_section(html: str) -> list[list[str]]:
    """Divide o HTML em seções (<ul class=cards-container>) e extrai card-names de cada uma.

    Retorna lista de listas de nomes (uma sublista por seção).
    """
    sections: list[list[str]] = []
    # Encontra blocos <ul class="cards-container"> ... </ul>
    ul_pattern = re.compile(
        r'<ul\s+class="cards-container"[^>]*>(.*?)</ul>', re.IGNORECASE | re.DOTALL
    )
    for ul_match in ul_pattern.finditer(html):
        ul_content = ul_match.group(1)
        cards: list[str] = []
        for m in CARD_ITEM_RE.finditer(ul_content):
            qty_str, card_name = m.group(1), m.group(2)
            card_name = _normalize_color(_decode_html_entities(card_name.strip()))
            # Adiciona qty_str como prefixo se for >1
            name = f"{qty_str}x {card_name}" if int(qty_str) > 1 else card_name
            cards.append(name)
        if cards:
            sections.append(cards)
    return sections


def _detect_hero_and_format(sections: list[list[str]]) -> tuple[str, list[str], list[str]]:
    """Detecta herói, arena (arma + equipamentos) e pool de deck das seções.

    Assume que a primeira seção é Hero / Weapon / Equipment.
    As demais seções são o pool do deck.
    Retorna (hero, arena, deck_pool_nomes).
    """
    hero = ""
    arena: list[str] = []
    pool: list[str] = []

    if not sections:
        return hero, arena, pool

    # Primeira seção: hero / weapon / equipment
    equip_section = sections[0]
    for item in equip_section:
        # Remove quantificador "Nx" se presente
        name = re.sub(r"^\d+\s*x\s*", "", item).strip()
        # A primeira entrada é o herói
        if not hero:
            # Verifica se parece herói (tem Hero no nome ou é a 1ª)
            hero = name
        else:
            arena.append(name)

    # Demais seções: pool do deck
    for sec in sections[1:]:
        pool.extend(sec)

    return hero, arena, pool


def fetch_decklist(url_or_path: str) -> str:
    """Retorna o HTML de uma URL ou o conteúdo de um arquivo local."""
    if url_or_path.startswith(("http://", "https://")):
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0 Safari/537.36"
            )
        }
        r = requests.get(url_or_path, headers=headers, timeout=15)
        r.raise_for_status()
        return r.text
    else:
        with open(url_or_path, encoding="utf-8") as f:
            return f.read()


def url_to_filename(url: str) -> str:
    """Deriva um nome de arquivo da URL da decklist."""
    # Pega o último segmento da path
    path = url.rstrip("/")
    slug = path.rsplit("/", 1)[-1] if "/" in path else "deck"
    # Remove trailing slash
    slug = slug.split("?")[0]
    # Remove prefixo numérico e trailing /
    slug = slug.strip("/")
    if not slug or slug == "decklists":
        slug = "deck"
    return slug[:60]  # limita tamanho


def convert_html_to_yaml(
    html: str,
    *,
    source_url: str = "",
    format_name: str = "silver-age",
) -> str | None:
    """Converte HTML de decklist para YAML no formato do projeto.

    Retorna string YAML, ou None se não conseguiu detectar herói.
    """
    sections = _split_cards_by_section(html)
    hero, arena, pool_nomes = _detect_hero_and_format(sections)

    if not hero:
        return None

    # Agrupa cartas por chave (nome + cor) e soma quantidades
    from collections import Counter

    counter: Counter[str] = Counter()
    for nome in pool_nomes:
        # Extrai quantidade do prefixo "Nx " (default 1)
        m_qty = re.match(r"^(\d+)\s*x\s*(.+)$", nome, re.IGNORECASE)
        if m_qty:
            qty = int(m_qty.group(1))
            cleaned = m_qty.group(2).strip()
        else:
            qty = 1
            cleaned = nome.strip()
        counter[cleaned] += qty

    lines = [
        f"# Decklist importada de: {source_url}" if source_url else "# Decklist importada",
        f'hero: "{hero}"',
        f"format: {format_name}",
        f'source: "{source_url}"' if source_url else 'source: ""',
        "",
        "# Arma + equipamentos disponíveis",
        "arena:",
    ]
    for eq in arena:
        lines.append(f'  - "{eq}"')

    lines.append("")
    lines.append("# Pool de deck")
    lines.append("deck_pool:")

    # Ordena por cor (red, yellow, blue, sem cor)
    def sort_key(item):
        key, _ = item
        base, color = _split_color(key)
        color_order = {"red": 0, "yellow": 1, "blue": 2}.get(color, 3)
        return (color_order, base.lower())

    for key, qty in sorted(counter.items(), key=sort_key):
        lines.append(f'  - {{qty: {qty}, card: "{key}"}}')

    return "\n".join(lines) + "\n"


def _split_color(key: str) -> tuple[str, str | None]:
    """Separa chave em (nome_base, cor)."""
    m = re.search(r"\((red|yellow|blue)\)$", key)
    if m:
        return key[: m.start()].strip(), m.group(1)
    return key, None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="URL da decklist no fabtcg.com ou arquivo HTML local")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Arquivo YAML de saída (padrão: data/decks/<slug>.yaml)",
    )
    parser.add_argument(
        "--format",
        default="silver-age",
        help="Formato do deck (padrão: silver-age)",
    )
    args = parser.parse_args()

    try:
        html = fetch_decklist(args.url)
    except (OSError, ValueError, requests.RequestException) as e:
        print(f"Erro ao baixar/ler: {e}", file=sys.stderr)
        return 1

    source = args.url
    yaml_str = convert_html_to_yaml(html, source_url=source, format_name=args.format)
    if yaml_str is None:
        print(
            "Erro: não foi possível detectar o herói na página. "
            "Verifique se a URL é uma página individual de decklist.",
            file=sys.stderr,
        )
        return 1

    if args.out:
        out_path = args.out
    else:
        slug = url_to_filename(args.url) if args.url.startswith(("http://", "https://")) else "deck"
        slug = slug.removesuffix(".yaml").removesuffix(".html")
        out_path = OUT_DIR / f"{slug}.yaml"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(yaml_str)

    print(f"{len(yaml_str.splitlines())} linhas escritas em {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
