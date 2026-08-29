"""Testes do ajuste manual de vida (comando life)."""

import pytest

from flesh_and_blood.combat import CombatError, adjust_life
from flesh_and_blood.models import Hero, new_game


@pytest.fixture()
def state():
    hero_a = Hero("Briar, Warden of Thorns", "Briar", 20, 4, ("Runeblade",), ())
    hero_b = Hero("Enigma", "Enigma", 20, 4, ("Illusionist",), ())
    return new_game(hero_a, hero_b)


def test_life_dano_negativo(state):
    notice = adjust_life(state, "A", -3)
    assert state.players["A"].life == 17
    assert "17" in notice.text
    assert "-3" in notice.text


def test_life_cura_positivo(state):
    notice = adjust_life(state, "B", 2)
    assert state.players["B"].life == 22
    assert "22" in notice.text
    assert "+2" in notice.text


def test_life_zero_levanta_erro(state):
    with pytest.raises(CombatError, match="diferente de zero"):
        adjust_life(state, "A", 0)


def test_life_lado_invalido_levanta_erro(state):
    with pytest.raises(CombatError, match="lado inválido"):
        adjust_life(state, "C", -1)
