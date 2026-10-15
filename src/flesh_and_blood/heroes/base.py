"""Base da arquitetura por herói: contrato e tipos comuns.

Cada herói com mecânica própria ganha uma ``HeroStrategy`` que sabe:
- planejar o turno (``plan_turn``) devolvendo um ``TurnPlan`` unificado;
- valorizar as cartas na mão (``hand_value_bonus``), usado pela defesa;
- emitir notas de contexto de defesa (``defense_notes``).

O herói genérico (sem motor próprio) usa ``plan_attack`` por baixo; heróis
especiais (Enigma, Bravo) sobrescrevem os métodos. Isso mantém o conhecimento
de cada herói isolado em um módulo, sem espalhar ``if hero_key == ...``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from flesh_and_blood.models import Card, ChainLink, GameState


@dataclass
class TurnPlan:
    """Plano de turno unificado, independente do herói.

    ``steps`` é a sequência executável pelo bot (tuplas (ação, parâmetro)):
    - ("pitch", key)        picha carta da mão;
    - ("play", key)         joga carta (action/aura/instant);
    - ("attack", key)       ataca com carta de ataque;
    - ("weapon", key)       ataca com arma;
    - ("cosmo", aura_key)   ataque de aura via Cosmo (Enigma);
    - ("activate_enigma",)  ativa a habilidade do herói (Enigma);
    - ("resolve",)          resolve o elo aberto.
    ``sequence`` é um resumo legível dos ataques/ações jogados (sem pitches).
    """

    steps: list[tuple] = field(default_factory=list)
    sequence: list[str] = field(default_factory=list)
    pitched: list[str] = field(default_factory=list)
    physical: int = 0
    arcane: int = 0
    lethal: bool = False
    notes: list[str] = field(default_factory=list)
    arsenal_suggestion: str | None = None

    @property
    def total(self) -> int:
        return self.physical + self.arcane


class HeroStrategy:
    """Contrato de estratégia de herói (classe base)."""

    hero_key: str = ""
    label: str = "genérico"

    def plan_turn(
        self,
        state: GameState,
        side: str,
        cards: dict[str, Card],
        *,
        opponent_life: int | None = None,
    ) -> TurnPlan:
        raise NotImplementedError

    def hand_value_bonus(self, card: Card) -> float:
        """Custo de oportunidade extra de gastar ``card`` (defesa/pitch).

        Valores altos = cartas que não queremos descartar (peças de motor).
        Somado ao valor genérico de ``defense.card_value``.
        """
        return 0.0

    def defense_notes(
        self, state: GameState, def_side: str, cards: dict[str, Card], link: ChainLink
    ) -> list[str]:
        """Notas contextuais mostradas ao se defender contra ``link``."""
        return []


def ward_base(card: Card | None) -> int:
    """Valor base de ward da carta (0 se não tiver)."""
    if card is None:
        return 0
    for kw in card.keywords:
        if kw.startswith("Ward") and kw.replace("Ward", "").strip().isdigit():
            return int(kw.replace("Ward", "").strip())
    return 0
