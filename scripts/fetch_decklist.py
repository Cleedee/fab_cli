#!/usr/bin/env python3
"""Baixa uma decklist (fabtcg.com ou fabrary.net) e converte para o formato YAML do projeto.

Uso:
    python scripts/fetch_decklist.py <url> [--out data/decks/<nome>.yaml]

Suporta:
    - fabtcg.com: página individual de decklist (HTML server-rendered)
    - fabrary.net: deck via API GraphQL (Cognito Identity Pool)

Também aceita arquivos HTML locais (útil para debug):
    python scripts/fetch_decklist.py /caminho/para/pagina.html

Dependências: PyYAML, requests.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import re
import sys
from datetime import UTC, datetime
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

# ---------------------------------------------------------------------------
# Fabrary (AWS AppSync + Cognito Identity Pool)
# ---------------------------------------------------------------------------
FABRARY_IDENTITY_POOL_ID = "us-east-2:e50f3ed7-32ed-4b22-a05e-10b3e7e03fe0"
FABRARY_GRAPHQL_ENDPOINT = "42xrd23ihbd47fjvsrt27ufpfe.appsync-api.us-east-2.amazonaws.com"
FABRARY_REGION = "us-east-2"

FABRARY_GET_DECK_QUERY = """\
query getDeck($deckId: ID!) {
  getDeck(deckId: $deckId) {
    name
    format
    hero { name }
    deckCards {
      cardIdentifier
      quantity
      sideboardQuantity
      card {
        name
        pitch
        types
      }
    }
  }
}"""


def _is_fabrary_url(url: str) -> bool:
    """Retorna True se a URL for do Fabrary."""
    return bool(re.match(r"https?://fabrary\.net/decks/", url))


def _extract_fabrary_deck_id(url: str) -> str:
    """Extrai o deckId da URL do Fabrary.

    Aceita formatos como:
        https://fabrary.net/decks/01M0NA0KYFSJCTM1ZSA3RAYM3D
        https://fabrary.net/decks/01M0NA0KYFSJCTM1ZSA3RAYM3D?tab=cards
    """
    m = re.search(r"/decks/([A-Za-z0-9]+)", url)
    if not m:
        raise ValueError(f"Não foi possível extrair deckId da URL: {url}")
    return m.group(1)


def _cognito_get_identity(session: requests.Session) -> str:
    """Obtém IdentityId do Cognito Identity Pool (acesso não-autenticado).

    Retorna identity_id.
    """
    url = f"https://cognito-identity.{FABRARY_REGION}.amazonaws.com/"
    payload = {
        "IdentityPoolId": FABRARY_IDENTITY_POOL_ID,
    }
    headers = {
        "Content-Type": "application/x-amz-json-1.1",
        "X-Amz-Target": "AWSCognitoIdentityService.GetId",
    }
    r = session.post(url, json=payload, headers=headers, timeout=10)
    r.raise_for_status()
    data = r.json()
    return data["IdentityId"]


def _cognito_get_credentials(session: requests.Session, identity_id: str) -> dict[str, str]:
    """Obtém credenciais temporárias do Cognito para uma identity.

    Retorna dict com access_key, secret_key, session_token.
    """
    url = f"https://cognito-identity.{FABRARY_REGION}.amazonaws.com/"
    payload = {
        "IdentityId": identity_id,
    }
    headers = {
        "Content-Type": "application/x-amz-json-1.1",
        "X-Amz-Target": "AWSCognitoIdentityService.GetCredentialsForIdentity",
    }
    r = session.post(url, json=payload, headers=headers, timeout=10)
    r.raise_for_status()
    data = r.json()
    creds = data["Credentials"]
    return {
        "access_key": creds["AccessKeyId"],
        "secret_key": creds["SecretKey"],
        "session_token": creds["SessionToken"],
    }


def _sha256_hex(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _hmac_sha256(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _get_signing_key(secret: str, date: str, region: str, service: str) -> bytes:
    k_date = _hmac_sha256(("AWS4" + secret).encode("utf-8"), date)
    k_region = _hmac_sha256(k_date, region)
    k_service = _hmac_sha256(k_region, service)
    k_signing = _hmac_sha256(k_service, "aws4_request")
    return k_signing


def _sigv4_sign_request(
    *,
    method: str,
    host: str,
    path: str,
    body: str,
    access_key: str,
    secret_key: str,
    session_token: str,
    region: str,
    service: str,
) -> dict[str, str]:
    """Assina uma requisição AWS SigV4 e retorna headers prontos."""
    now = datetime.now(UTC)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")

    payload_hash = _sha256_hex(body)

    # Headers obrigatórios para assinatura
    signed_headers_list = ["content-type", "host", "x-amz-date", "x-amz-security-token"]
    signed_headers_str = ";".join(signed_headers_list)

    canonical_headers = (
        f"content-type:application/json; charset=UTF-8\n"
        f"host:{host}\n"
        f"x-amz-date:{amz_date}\n"
        f"x-amz-security-token:{session_token}\n"
    )

    canonical_querystring = ""
    canonical_request = (
        f"{method}\n{path}\n{canonical_querystring}\n"
        f"{canonical_headers}\n{signed_headers_str}\n{payload_hash}"
    )

    credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            amz_date,
            credential_scope,
            _sha256_hex(canonical_request),
        ]
    )

    signing_key = _get_signing_key(secret_key, date_stamp, region, service)
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    authorization = (
        f"AWS4-HMAC-SHA256 Credential={access_key}/{credential_scope}, "
        f"SignedHeaders={signed_headers_str}, "
        f"Signature={signature}"
    )

    return {
        "Content-Type": "application/json; charset=UTF-8",
        "Host": host,
        "x-amz-date": amz_date,
        "x-amz-security-token": session_token,
        "Authorization": authorization,
    }


def _fetch_fabrary_graphql(deck_id: str) -> dict:
    """Busca dados do deck via API GraphQL do Fabrary (Cognito Identity Pool)."""
    session = requests.Session()

    identity_id = _cognito_get_identity(session)
    creds = _cognito_get_credentials(session, identity_id)

    host = FABRARY_GRAPHQL_ENDPOINT
    path = "/graphql"
    body = json.dumps({"query": FABRARY_GET_DECK_QUERY, "variables": {"deckId": deck_id}})

    headers = _sigv4_sign_request(
        method="POST",
        host=host,
        path=path,
        body=body,
        access_key=creds["access_key"],
        secret_key=creds["secret_key"],
        session_token=creds["session_token"],
        region=FABRARY_REGION,
        service="appsync",
    )
    # Headers necessários para WAF do AppSync (não assinados)
    headers["Referer"] = "https://fabrary.net/"
    headers["User-Agent"] = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"
    )

    r = session.post(f"https://{host}{path}", data=body, headers=headers, timeout=15)
    r.raise_for_status()
    data = r.json()

    if "errors" in data:
        raise ValueError(f"GraphQL errors: {data['errors']}")
    deck = data.get("data", {}).get("getDeck")
    if not deck:
        raise ValueError("Deck não encontrado no Fabrary.")
    return deck


def _pitch_to_color(pitch: int | None) -> str | None:
    """Converte pitch numérico do Fabrary para nome de cor."""
    return {1: "red", 2: "yellow", 3: "blue"}.get(pitch or 0)


def _fabrary_card_key(name: str, pitch: int | None) -> str:
    """Gera a chave da carta no formato do projeto a partir dos dados do Fabrary.

    Cartas sem pitch (equipamento, arma, herói) usam só o nome.
    Cartas com pitch usam 'Nome (cor)'.
    """
    color = _pitch_to_color(pitch)
    return f"{name} ({color})" if color else name


def convert_fabrary_to_yaml(
    deck: dict,
    *,
    source_url: str = "",
    format_name: str = "silver-age",
) -> str:
    """Converte dados do deck do Fabrary para YAML no formato do projeto.

    deck é o dict retornado pela API GraphQL (campo 'getDeck').
    """
    from collections import Counter

    hero_name = deck["hero"]["name"]
    cards = deck["deckCards"]

    # Arena: weapon + equipment com qty > 0
    arena: list[str] = []
    # Deck pool: tudo mais com qty > 0
    pool_counter: Counter[str] = Counter()

    for entry in cards:
        card = entry["card"]
        qty = entry.get("quantity") or 0
        types = card.get("types", [])
        pitch = card.get("pitch")
        name = card["name"]

        key = _fabrary_card_key(name, pitch)

        if qty > 0:
            if "Weapon" in types or "Equipment" in types:
                arena.append(key)
            else:
                pool_counter[key] += qty

    # Ordena arena por nome
    arena.sort(key=lambda k: k.lower())

    lines = [
        f"# Decklist importada de: {source_url}" if source_url else "# Decklist importada",
        f'hero: "{hero_name}"',
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

    def sort_key(item):
        key, _ = item
        base, color = _split_color(key)
        color_order = {"red": 0, "yellow": 1, "blue": 2}.get(color, 3)
        return (color_order, base.lower())

    for key, qty in sorted(pool_counter.items(), key=sort_key):
        lines.append(f'  - {{qty: {qty}, card: "{key}"}}')

    return "\n".join(lines) + "\n"


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
    parser.add_argument(
        "url",
        help="URL da decklist (fabtcg.com, fabrary.net) ou arquivo HTML local",
    )
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

    source = args.url
    yaml_str: str | None = None

    if _is_fabrary_url(source):
        try:
            deck_id = _extract_fabrary_deck_id(source)
            deck = _fetch_fabrary_graphql(deck_id)
            yaml_str = convert_fabrary_to_yaml(deck, source_url=source, format_name=args.format)
        except (ValueError, requests.RequestException) as e:
            print(f"Erro ao baixar deck do Fabrary: {e}", file=sys.stderr)
            return 1
    else:
        try:
            html = fetch_decklist(source)
        except (OSError, ValueError, requests.RequestException) as e:
            print(f"Erro ao baixar/ler: {e}", file=sys.stderr)
            return 1

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
        slug = url_to_filename(source) if source.startswith(("http://", "https://")) else "deck"
        slug = slug.removesuffix(".yaml").removesuffix(".html")
        out_path = OUT_DIR / f"{slug}.yaml"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(yaml_str)

    print(f"{len(yaml_str.splitlines())} linhas escritas em {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
