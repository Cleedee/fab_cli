import pytest

from fresh_and_blood.models import (
    Card,
    ChainLink,
    Color,
    GameState,
    Hero,
    new_game,
    pay_cost,
    pitch_card,
)


def make_card(**kwargs) -> Card:
    defaults = {
        "key": "Snatch (red)",
        "name": "Snatch",
        "color": Color.RED,
        "pitch": 1,
        "cost": 0,
        "power": 2,
        "defense": 2,
        "types": ("Elemental", "Lightning", "Runeblade", "Action", "Attack"),
        "keywords": ("Go again",),
        "text": "",
        "rarity": "C",
        "sa_legal": True,
    }
    return Card(**{**defaults, **kwargs})


@pytest.fixture
def heroes():
    briar = Hero(
        key="Briar, Warden of Thorns",
        name="Briar, Warden of Thorns",
        life=20,
        intellect=4,
        classes=("Runeblade",),
        talents=("Earth", "Lightning"),
    )
    enigma = Hero(
        key="Enigma",
        name="Enigma",
        life=20,
        intellect=4,
        classes=("Illusionist",),
        talents=("Mystic",),
    )
    return briar, enigma


def test_new_game_starts_correctly(heroes):
    briar, enigma = heroes
    state = new_game(briar, enigma)
    assert state.players["A"].life == 20
    assert state.players["B"].life == 20
    assert state.active_player == "A"
    assert state.players["A"].action_points == 1
    assert state.players["B"].action_points == 0


def test_damage_and_heal(heroes):
    briar, enigma = heroes
    state = new_game(briar, enigma)
    state.players["B"].damage(5)
    assert state.players["B"].life == 15
    state.players["B"].heal(2)
    assert state.players["B"].life == 17


def test_chain_link_math():
    link = ChainLink(
        attacker="A", card_key="Snatch (red)", total_damage=4, blocked_by=["Look Tuff (red)"]
    )
    link.blocked_damage = 3
    assert link.damage_remaining == 1


def test_chain_link_untblocked():
    link = ChainLink(attacker="A", card_key="Star Fall", total_damage=1)
    assert link.damage_remaining == 1


def test_save_load_roundtrip(heroes):
    briar, enigma = heroes
    state = new_game(briar, enigma)
    state.players["A"].hand.append("Snatch (red)")
    state.players["A"].pitch_pool = 3
    state.players["B"].damage(6)
    state.chain.append(ChainLink(attacker="A", card_key="Star Fall", total_damage=1))

    data = state.to_dict()
    restored = GameState.from_dict(data)
    assert restored == state


def test_pitch_and_pay():
    card = make_card()
    assert pitch_card(card) == 1
    with pytest.raises(ValueError):
        pitch_card(make_card(key="Star Fall", name="Star Fall", color=None, pitch=None))


def test_pay_cost_requires_resources():
    from fresh_and_blood.models import PlayerState

    player = PlayerState(hero_key="Enigma", pitch_pool=2)
    pay_cost(player, 2)
    assert player.pitch_pool == 0
    with pytest.raises(ValueError):
        pay_cost(player, 1)
