from flesh_and_blood.carddb import load_cards
from flesh_and_blood.models import Color


def test_registry_loads() -> None:
    cards = load_cards()
    assert len(cards) > 60


def test_heroes_present_and_legal() -> None:
    cards = load_cards()
    briar = cards["Briar, Warden of Thorns"]
    enigma = cards["Enigma"]
    assert briar.sa_legal and "Young" in briar.types
    assert enigma.sa_legal and "Young" in enigma.types


def test_token_keywords() -> None:
    cards = load_cards()
    shield = cards["Spectral Shield"]
    earth = cards["Embodiment of Earth"]
    lightning = cards["Embodiment of Lightning"]
    assert "Ward 1" in shield.keywords
    # Embodiments são auras sem ward: Earth dá +1{d} na defesa, Lightning dá go again
    assert not any(kw.lower().startswith("ward") for kw in earth.keywords)
    assert "+1{d}" in earth.text
    assert "go again" in lightning.text


def test_colored_keys_parse() -> None:
    cards = load_cards()
    snatch = cards["Snatch (red)"]
    assert snatch.color is Color.RED
    assert snatch.pitch == 1
    assert snatch.is_attack


def test_every_card_has_types() -> None:
    for key, card in load_cards().items():
        assert card.types, f"carta sem tipos: {key}"
