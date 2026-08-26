"""Cliente compartilhado para a API GraphQL do Fabrary.

Fornece autenticação Cognito Identity Pool + AWS SigV4 e consulta getDeck.
Usado por scripts/fetch_decklist.py e scripts/build_cards.py.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime

import requests

IDENTITY_POOL_ID = "us-east-2:e50f3ed7-32ed-4b22-a05e-10b3e7e03fe0"
GRAPHQL_ENDPOINT = "42xrd23ihbd47fjvsrt27ufpfe.appsync-api.us-east-2.amazonaws.com"
REGION = "us-east-2"

GET_DECK_QUERY = """\
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
        cost
        power
        defense
        types
        keywords
        functionalTextPlain
        color
        rarity
        silverAgeLegal
        silverAgeBanned
      }
    }
  }
}
"""

_PITCH_MAP: dict[int, str] = {1: "red", 2: "yellow", 3: "blue"}


def pitch_to_color(pitch: int | None) -> str | None:
    """Converte pitch numérico do Fabrary para nome de cor."""
    return _PITCH_MAP.get(pitch or 0)


def card_key(name: str, pitch: int | None) -> str:
    """Gera a chave da carta no formato do projeto.

    Cartas sem pitch (equipamento, arma, herói) usam só o nome.
    Cartas com pitch usam ``'Nome (cor)'``.
    """
    color = pitch_to_color(pitch)
    return f"{name} ({color})" if color else name


def extract_card_data(card: dict, pitch: int | None) -> dict:
    """Extrai dados relevantes de uma carta do Fabrary para o registro do projeto.

    Retorna dict compatível com o formato de ``data/cards.yaml``.
    """
    keywords = [
        kw.strip()
        for chunk in (card.get("keywords") or [])
        if chunk
        for kw in chunk.split(",")
        if kw.strip()
    ]
    return {
        "name": card["name"],
        "color": pitch_to_color(pitch),
        "pitch": pitch,
        "cost": _num(card.get("cost")),
        "power": _num(card.get("power")),
        "defense": _num(card.get("defense")),
        "types": card.get("types") or [],
        "keywords": keywords,
        "text": card.get("functionalTextPlain") or "",
        "rarity": card.get("rarity") or "",
        "sa_legal": bool(card.get("silverAgeLegal")) and not card.get("silverAgeBanned"),
    }


def _num(value: str | None) -> int | None:
    if value is None:
        return None
    v = str(value).strip()
    return int(v) if v.isdigit() else None


# ---------------------------------------------------------------------------
# Autenticação AWS Cognito + SigV4
# ---------------------------------------------------------------------------


def _cognito_get_identity(session: requests.Session) -> str:
    """Obtém IdentityId do Cognito Identity Pool (acesso não-autenticado)."""
    url = f"https://cognito-identity.{REGION}.amazonaws.com/"
    payload = {"IdentityPoolId": IDENTITY_POOL_ID}
    headers = {
        "Content-Type": "application/x-amz-json-1.1",
        "X-Amz-Target": "AWSCognitoIdentityService.GetId",
    }
    r = session.post(url, json=payload, headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()["IdentityId"]


def _cognito_get_credentials(session: requests.Session, identity_id: str) -> dict[str, str]:
    """Obtém credenciais temporárias do Cognito para uma identity."""
    url = f"https://cognito-identity.{REGION}.amazonaws.com/"
    payload = {"IdentityId": identity_id}
    headers = {
        "Content-Type": "application/x-amz-json-1.1",
        "X-Amz-Target": "AWSCognitoIdentityService.GetCredentialsForIdentity",
    }
    r = session.post(url, json=payload, headers=headers, timeout=10)
    r.raise_for_status()
    creds = r.json()["Credentials"]
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
    return _hmac_sha256(k_service, "aws4_request")


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

    signed_headers_list = ["content-type", "host", "x-amz-date", "x-amz-security-token"]
    signed_headers_str = ";".join(signed_headers_list)

    canonical_headers = (
        f"content-type:application/json; charset=UTF-8\n"
        f"host:{host}\n"
        f"x-amz-date:{amz_date}\n"
        f"x-amz-security-token:{session_token}\n"
    )

    canonical_request = (
        f"{method}\n{path}\n\n{canonical_headers}\n{signed_headers_str}\n{payload_hash}"
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


# ---------------------------------------------------------------------------
# Consulta GraphQL
# ---------------------------------------------------------------------------


def get_deck(deck_id: str) -> dict:
    """Busca dados do deck via API GraphQL do Fabrary.

    Retorna o dict do deck (campo ``getDeck`` da resposta GraphQL).
    """
    session = requests.Session()

    identity_id = _cognito_get_identity(session)
    creds = _cognito_get_credentials(session, identity_id)

    host = GRAPHQL_ENDPOINT
    path = "/graphql"
    body = json.dumps({"query": GET_DECK_QUERY, "variables": {"deckId": deck_id}})

    headers = _sigv4_sign_request(
        method="POST",
        host=host,
        path=path,
        body=body,
        access_key=creds["access_key"],
        secret_key=creds["secret_key"],
        session_token=creds["session_token"],
        region=REGION,
        service="appsync",
    )
    # Headers para WAF (não assinados)
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


def extract_deck_cards(deck: dict) -> list[dict]:
    """Extrai dados completos de cada carta de um deck.

    Retorna lista de dicts com ``key`` (chave do projeto), ``name``,
    ``pitch`` e todos os campos de ``extract_card_data``.
    """
    result = []
    for entry in deck.get("deckCards", []):
        qty = entry.get("quantity") or 0
        if qty <= 0:
            continue
        inner = entry.get("card", {})
        pitch = inner.get("pitch")
        name = inner["name"]
        result.append(
            {
                "key": card_key(name, pitch),
                "name": name,
                "pitch": pitch,
                "quantity": qty,
                **extract_card_data(inner, pitch),
            }
        )
    return result
