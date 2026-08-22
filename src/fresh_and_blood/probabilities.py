"""Probabilidades de compra (hipergeométrica) para apoio a decisão.

Funções puras: o chamador informa o tamanho do deck desconhecido, quantas
cópias "procura" e quantas cartas serão compradas. Serve tanto para
"chance de comprar meu Snatch" quanto para "chance de pichar azul"
(cópias = cartas azuis restantes).
"""

from math import comb


def hypergeom_pmf(deck_size: int, successes: int, draws: int, wanted: int) -> float:
    """P(exatamente `wanted` sucessos em `draws` compras de um baralho de `deck_size`)."""
    if min(deck_size, successes, draws, wanted) < 0:
        raise ValueError("argumentos não podem ser negativos")
    if successes > deck_size:
        raise ValueError("sucessos maiores que o baralho")
    if wanted > min(draws, successes):
        return 0.0
    failures = deck_size - successes
    avoided = draws - wanted
    if avoided > failures:
        return 0.0
    return comb(successes, wanted) * comb(failures, avoided) / comb(deck_size, draws)


def prob_exactly(deck_size: int, copies: int, draws: int, count: int) -> float:
    """P(comprar exatamente `count` das `copies` em `draws`)."""
    return hypergeom_pmf(deck_size, copies, draws, count)


def prob_at_least(deck_size: int, copies: int, draws: int, min_count: int = 1) -> float:
    """P(comprar pelo menos `min_count` das `copies` em `draws`)."""
    upper = min(draws, copies)
    if min_count > upper:
        return 0.0
    return sum(hypergeom_pmf(deck_size, copies, draws, k) for k in range(min_count, upper + 1))


def prob_at_least_one(deck_size: int, copies: int, draws: int) -> float:
    """Atalho comum: P(comprar ao menos 1 das cópias)."""
    return prob_at_least(deck_size, copies, draws, 1)
