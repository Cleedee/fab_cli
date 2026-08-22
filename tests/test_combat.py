import pytest

from fresh_and_blood.carddb import load_cards
from fresh_and_blood.combat import (
    CombatError,
    boost_link,
    deal_arcane,
    declare_attack,
    defend_link,
    end_turn,
    pitch,
    play_action,
    resolve_link,
    set_arcane_on_link,
    spend_ward,
    start_turn,
    use_equipment_defense,
    ward_value,
)
from fresh_and_blood.models import Card, ChainLink, Color, GameState, Hero, new_game


@pytest.fixture(scope="module")
def cards():
    return load_cards()


@pytest.fixture
def state():
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
    s = new_game(briar, enigma)
    a = s.players["A"]
    a.hand = [
        "Sizzle (red)",
        "Snatch (red)",
        "Arcanic Shockwave (red)",
        "Weave Lightning (red)",
        "Stinging Sprite (red)",
        "Evergreen (red)",
    ]
    b = s.players["B"]
    b.hand = ["Unmovable (blue)", "Sizzle (red)", "Snatch (red)"]
    return s


def plain_action_card() -> Card:
    """Non-attack action sem Go Again, para testar consumo de AP."""
    return Card(
        key="Plain Action (red)",
        name="Plain Action",
        color=Color.RED,
        pitch=1,
        cost=0,
        power=None,
        defense=2,
        types=("Generic", "Action"),
        keywords=(),
        text="",
        rarity="C",
        sa_legal=True,
    )


# --- turno ---------------------------------------------------------------


def test_start_turn_resets_counters(state):
    a = state.players["A"]
    a.action_points = 0
    a.equipment_used_this_turn.append("Nullrune Boots")
    start_turn(state, "A")
    assert a.action_points == 1 and a.equipment_used_this_turn == []


def test_embodiment_of_earth_dies_at_own_action_phase(state):
    a = state.players["A"]
    a.add_aura("Embodiment of Earth")  # sobreviveu ao turno do oponente
    notices = start_turn(state, "A")
    assert a.auras.get("Embodiment of Earth") is None
    assert any("Embodiment of Earth" in n.text for n in notices)


def test_end_turn_switches_active(state):
    end_turn(state)
    assert state.active_player == "B"


# --- recursos ------------------------------------------------------------


def test_pitch_adds_resources(state, cards):
    a = state.players["A"]
    gained = pitch(state, "A", "Evergreen (red)", cards)  # red = 1 pitch
    assert gained == 1 and a.pitch_pool == 1 and "Evergreen (red)" not in a.hand


def test_play_action_without_go_again_consumes_ap(state, cards):
    registry = {**cards, "Plain Action (red)": plain_action_card()}
    state.players["A"].hand.append("Plain Action (red)")
    play_action(state, "A", "Plain Action (red)", registry)
    assert state.players["A"].action_points == 0


def test_play_action_with_go_again_keeps_ap(state, cards):
    play_action(state, "A", "Sizzle (red)", cards)
    assert state.players["A"].action_points == 1


def test_no_ap_blocks_action(state, cards):
    registry = {**cards, "Plain Action (red)": plain_action_card()}
    a = state.players["A"]
    a.hand.append("Plain Action (red)")
    a.action_points = 0
    with pytest.raises(CombatError, match="action points"):
        play_action(state, "A", "Plain Action (red)", registry)


def test_defense_reaction_not_playable_as_action(state, cards):
    state.players["A"].hand.append("Sigil of Suffering (red)")
    with pytest.raises(CombatError, match="Defense Reaction"):
        play_action(state, "A", "Sigil of Suffering (red)", cards)


def test_briar_second_non_attack_creates_lightning(state, cards):
    a = state.players["A"]
    play_action(state, "A", "Sizzle (red)", cards)  # 1ª (go again)
    notices = play_action(state, "A", "Weave Lightning (red)", cards)  # 2ª
    assert a.auras.get("Embodiment of Lightning") == [0]
    assert any("Embodiment of Lightning" in n.text for n in notices)


# --- ataques -------------------------------------------------------------


def test_declare_attack_from_hand(state, cards):
    a = state.players["A"]
    link = declare_attack(state, "A", "Arcanic Shockwave (red)", cards)
    assert link.total_damage == 4
    assert "Arcanic Shockwave (red)" not in a.hand
    assert a.action_points == 0  # sem go again: consumiu o AP do turno


def test_embodiment_of_lightning_grants_go_again(state, cards):
    a = state.players["A"]
    a.add_aura("Embodiment of Lightning")
    declare_attack(state, "A", "Snatch (red)", cards)
    assert a.action_points == 1  # gastou e recebeu de volta
    assert a.auras.get("Embodiment of Lightning") is None


def test_weapon_once_per_turn_costs_ap_and_resources(state, cards):
    a = state.players["A"]
    a.pitch_pool = 2
    link = declare_attack(state, "A", "Star Fall", cards, is_weapon=True, resource_cost=1)
    assert link.total_damage == 1
    assert a.pitch_pool == 1 and a.action_points == 0
    with pytest.raises(CombatError, match="já atacou"):
        declare_attack(state, "A", "Star Fall", cards, is_weapon=True, resource_cost=1)


def test_boost_and_arcane_on_link(state, cards):
    declare_attack(state, "A", "Arcanic Shockwave (red)", cards)
    boost_link(state, "A", 3, "Sizzle (red)")
    set_arcane_on_link(state, "A", 1, "fusão Lightning")
    link = [l for l in state.chain if not l.resolved][-1]
    assert link.total_damage == 7 and link.arcane_damage == 1


# --- defesa --------------------------------------------------------------


def test_defend_basic_math(state, cards):
    declare_attack(state, "A", "Arcanic Shockwave (red)", cards)  # 4 power
    b = state.players["B"]
    defend_link(state, "B", ["Unmovable (blue)"], cards)  # block 5
    result = resolve_link(state, cards)
    assert result["physical"] == 0 and b.life == 20


def test_partial_block_hits(state, cards):
    declare_attack(state, "A", "Arcanic Shockwave (red)", cards)  # 4
    b = state.players["B"]
    b.hand = ["Sizzle (red)", "Snatch (red)"]  # 2 + 2
    defend_link(state, "B", ["Sizzle (red)", "Snatch (red)"], cards)
    result = resolve_link(state, cards)
    assert result["physical"] == 0  # 4 bloqueado por 4


def test_embodiment_of_earth_gives_plus_1d_to_non_attack(state, cards):
    declare_attack(state, "A", "Arcanic Shockwave (red)", cards)  # 4
    b = state.players["B"]
    b.add_aura("Embodiment of Earth")  # cenário: defensor Briar com a aura ativa
    b.hand = ["Sizzle (red)", "Snatch (red)"]
    defend_link(state, "B", ["Sizzle (red)", "Snatch (red)"], cards)
    link = [l for l in state.chain if not l.resolved][-1]
    # Sizzle (non-attack): 2+1 | Snatch (attack action): 2 sem bônus
    assert link.blocked_damage == 5
    resolve_link(state, cards)


def test_dominate_limits_two_cards_max(state, cards):
    declare_attack(state, "A", "Arcanic Shockwave (red)", cards, dominate=True)
    with pytest.raises(CombatError, match="Dominate"):
        defend_link(
            state,
            "B",
            ["Unmovable (blue)", "Sizzle (red)", "Snatch (red)"],
            cards,
        )


def test_dominate_only_one_action_card(state, cards):
    declare_attack(state, "A", "Arcanic Shockwave (red)", cards, dominate=True)
    with pytest.raises(CombatError, match="Dominate"):
        defend_link(state, "B", ["Sizzle (red)", "Snatch (red)"], cards)


def test_equipment_defense_once_per_turn(state, cards):
    declare_attack(state, "A", "Stinging Sprite (red)", cards)  # 3
    gained = use_equipment_defense(state, "B", "Blade Beckoner Helm", cards, extra_defense=1)
    assert gained == 2  # 1 base + 1 extra manual
    with pytest.raises(CombatError, match="já foi usado"):
        use_equipment_defense(state, "B", "Blade Beckoner Helm", cards)


def test_stinging_sprite_defending_pings_arcane(state, cards):
    declare_attack(state, "A", "Snatch (red)", cards)
    state.players["B"].hand.append("Stinging Sprite (red)")
    notices = defend_link(state, "B", ["Stinging Sprite (red)"], cards)
    assert any("arcane" in n.text or "arcano" in n.text for n in notices)


# --- ward / arcano / resolução -------------------------------------------


def test_spectral_shield_ward_prevents_and_token_vanishes(state, cards):
    b = state.players["B"]
    b.add_aura("Spectral Shield", counters=1)  # ward 2
    assert ward_value(b, "Spectral Shield") == 2
    declare_attack(state, "A", "Arcanic Shockwave (red)", cards)  # 4
    notices = spend_ward(state, "B", "Spectral Shield", needed=4)
    assert any("previne 2" in n.text for n in notices)
    result = resolve_link(state, cards, ward_prevented=2)
    assert result["physical"] == 2
    assert b.life == 18
    assert b.auras.get("Spectral Shield") is None


def test_arcane_bypasses_block_but_barrier_helps(state, cards):
    declare_attack(state, "A", "Arcanic Shockwave (red)", cards)
    set_arcane_on_link(state, "A", 1, "fusão Lightning")
    state.players["B"].hand.append("Sigil of Suffering (red)")  # DR, def 3
    defend_link(state, "B", ["Sigil of Suffering (red)"], cards)  # bloqueia 3 dos 4
    result = resolve_link(state, cards, arcane_prevented=1)  # Arcane Barrier 1
    assert result["physical"] == 1 and result["arcane"] == 0
    assert state.players["B"].life == 19


def test_briar_creates_earth_on_first_action_damage(state, cards):
    declare_attack(state, "A", "Arcanic Shockwave (red)", cards)
    result = resolve_link(state, cards)  # 4 não bloqueado
    a = state.players["A"]
    assert result["hit"] and result["physical"] == 4
    assert a.first_attack_damage_done
    assert a.auras.get("Embodiment of Earth") == [0]


def test_briar_no_second_earth_same_turn(state, cards):
    a = state.players["A"]
    a.action_points = 9
    declare_attack(state, "A", "Snatch (red)", cards, go_again_earned=True)
    resolve_link(state, cards)
    declare_attack(state, "A", "Stinging Sprite (red)", cards, go_again_earned=True)
    resolve_link(state, cards)
    assert a.auras.get("Embodiment of Earth") == [0]


def test_blocked_attack_still_creates_earth_if_arcane_hits(state, cards):
    # Fusão da Shockwave: mesmo bloqueada fisicamente, o arcano conta como dano.
    declare_attack(state, "A", "Arcanic Shockwave (red)", cards)
    set_arcane_on_link(state, "A", 1, "fusão")
    defend_link(state, "B", ["Unmovable (blue)"], cards)
    resolve_link(state, cards, arcane_prevented=0)
    a = state.players["A"]
    assert a.first_attack_damage_done
    assert a.auras.get("Embodiment of Earth") == [0]


def test_weapon_does_not_create_earth(state, cards):
    a = state.players["A"]
    a.pitch_pool = 2
    declare_attack(state, "A", "Star Fall", cards, is_weapon=True, resource_cost=1)
    resolve_link(state, cards)
    assert not a.first_attack_damage_done
    assert a.auras.get("Embodiment of Earth") is None


def test_deal_arcane_direct(state):
    dealt = deal_arcane(state, "B", 2)
    assert dealt == 2 and state.players["B"].life == 18
    assert deal_arcane(state, "B", 2, prevented=3) == 0


def test_chain_roundtrip_survives_serialization(state, cards):
    declare_attack(state, "A", "Arcanic Shockwave (red)", cards)
    boost_link(state, "A", 3)
    data = state.to_dict()
    restored = GameState.from_dict(data)
    link = restored.chain[-1]
    assert isinstance(link, ChainLink) and link.total_damage == 7
