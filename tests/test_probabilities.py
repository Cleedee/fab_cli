"""Testes de probabilidades hipergeométricas."""

import pytest

from fresh_and_blood.probabilities import (
    hypergeom_pmf,
    prob_at_least_one,
    prob_exactly,
)


def test_pmf_soma_1():
    total = sum(hypergeom_pmf(40, 3, 5, k) for k in range(6))
    assert total == pytest.approx(1.0)


def test_identidade_do_complemento():
    # P(X>=1) == 1 - P(X=0)
    p0 = hypergeom_pmf(40, 2, 4, 0)
    assert prob_at_least_one(40, 2, 4) == pytest.approx(1 - p0)


def test_valores_conhecidos():
    # Deck de 40, 3 cópias, comprando 1: 3/40
    assert prob_exactly(40, 3, 1, 1) == pytest.approx(3 / 40)
    # Comprando o baralho inteiro com cópias > 0: certeza
    assert prob_at_least_one(40, 3, 40) == pytest.approx(1.0)


def test_casos_de_borda():
    assert prob_at_least_one(40, 0, 4) == 0.0
    with pytest.raises(ValueError):
        hypergeom_pmf(10, 11, 2, 1)
    with pytest.raises(ValueError):
        hypergeom_pmf(-1, 1, 1, 1)
    # quer mais do que consegue comprar -> zero
    assert prob_exactly(40, 3, 2, 3) == 0.0


def test_pitch_azul():
    # Restam 20 cartas desconhecidas, 8 azuis; pichar nas próximas 2 compras.
    p = prob_at_least_one(20, 8, 2)
    assert 0.5 < p < 0.9


def test_prob_at_least_certeza_quando_min_count_zero():
    # P(pegar ao menos 0) = 1.0 sempre
    assert prob_at_least_one(40, 5, 10) < 1.0  # sanity: P(>=1) < 1
    from fresh_and_blood.probabilities import prob_at_least

    assert prob_at_least(40, 5, 10, 0) == 1.0
    assert prob_at_least(40, 0, 10, 0) == 1.0
