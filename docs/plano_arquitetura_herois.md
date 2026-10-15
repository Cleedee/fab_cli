# Arquitetura por herói (estratégias de turno, defesa e matchup)

Documento de implementação da refatoração que organiza o código por **tipo de
herói**, substituindo as cadeias de `if hero_key == ...` por um *registry* de
estratégias. Também é onde vive o **modelo de ameaça** do oponente (ex.: o crush
do Bravo), que transforma os planos de matchup em código executável
(`docs/enigma_vs_bravo.md`).

## Problema anterior

- `attack.py` (613 linhas) misturava o planejador **genérico** (Briar/Kayo) com
  o planejador **específico do Enigma** (`plan_enigma`).
- `defense.py` tinha nomes de cartas do Enigma *hardcoded* em `card_value`
  (`Spectral Manifestations` +6, etc.) — conhecimento de herói vazando para o
  módulo genérico.
- `bot.py` e `app.py` decidiam por `if me.hero_key == "Enigma": ... else: ...`.
- Não havia lugar para o conhecimento de **matchup** (ex.: Enigma vs Bravo).

## Nova estrutura

```
src/flesh_and_blood/heroes/
  __init__.py    # registry: strategy_for(hero_key) + reexports
  base.py        # TurnPlan, HeroStrategy, ward_base
  generic.py     # GenericStrategy / plan_generic_turn (envolve plan_attack)
  enigma.py      # plan_enigma + EnigmaStrategy (motor Cosmo/auras)
  bravo.py       # BravoStrategy + CrushThreat + crush_threat (ameaça)
  matchups.py    # phantasm_risk, opponent_threat, threat_report
```

### `base.HeroStrategy` — o contrato

| Método | Responsabilidade |
|---|---|
| `plan_turn(state, side, cards, *, opponent_life=None) -> TurnPlan` | linha do turno em steps executáveis |
| `hand_value_bonus(card) -> float` | custo de oportunidade extra de gastar a carta (defesa/pitch) |
| `defense_notes(state, side, cards, link) -> list[str]` | avisos contextuais ao defender |

`TurnPlan` é o **plano unificado** (steps, sequence, physical, arcane, lethal,
pitched, notes, arsenal_suggestion). O vocabulário de `steps` é comum a todos os
heróis:

| step | ação |
|---|---|
| `("pitch", key)` | pichar carta |
| `("play", key)` | jogar carta (action/aura/instant) |
| `("attack", key)` | atacar com carta |
| `("weapon", key)` | atacar com arma |
| `("cosmo", aura_key)` | ataque de aura via Cosmo (Enigma) |
| `("activate_enigma",)` | habilidade do herói (Enigma) |
| `("resolve",)` | resolver o elo aberto |

Assim, **um único executor** em `bot.py` roda qualquer herói.

### Registry

```python
from flesh_and_blood.heroes import strategy_for
strategy = strategy_for(me.hero_key)      # Enigma/Bravo/… ou GenericStrategy
plan = strategy.plan_turn(state, side, cards, opponent_life=opp_life)
```

Herói sem estratégia própria → `GenericStrategy` (usa `plan_attack`).

## Modelo de ameaça (matchup em código)

`bravo.crush_threat(opp, cards)` estima o golpe do Bravo: se o arsenal tiver um
ataque com **crush**, devolve `CrushThreat(card_key, power=base+2, dominate=True,
effect, ready)` — o `+2`/Dominate vêm da habilidade do herói (virar a carta do
arsenal). `matchups.opponent_threat(state, side, cards)` despacha por herói do
oponente e é consumido por:

- `plan_enigma` → `threat_report` anota a ameaça de crush e, se o oponente tiver
  um attack action **não-Illusionist de 6+{p}** (`phantasm_risk`), **evita**
  atacar com `Enigma Chimera`/`Spears of Surreality` (Phantasm, CR 8.3.13).

## Defesa hero-aware

`defense.card_value` ficou genérico. `suggest_defense(..., value_bonus=fn)` recebe
o bônus específico do herói; bot e app passam
`strategy_for(defender).hand_value_bonus`. O bônus do Enigma preserva motor/charge
e o `Unflinching Foothold` (anti-Dominate):

| carta | bônus |
|---|---|
| Spectral Manifestations / Solitary Companion | +6.0 |
| Astral Etchings | +5.0 |
| Unflinching Foothold | +5.0 |

## Como adicionar um novo herói

1. Crie `heroes/<heroi>.py` com uma `HeroStrategy` (ou reuse `GenericStrategy`).
2. Sobrescreva `plan_turn`/`hand_value_bonus`/`defense_notes` só onde diferir.
3. Registre em `heroes/__init__.py` (`_STRATEGIES[hero_key] = ...`).
4. Se o herói for um **oponente** relevante, adicione o modelo de ameaça em
   `heroes/matchups.py` (como o `crush_threat`).
5. Teste em `tests/test_heroes.py`.

## Impacto

- `attack.py` (613→333 linhas) agora é 100% genérico.
- `defense.py` sem nomes de cartas de herói.
- `bot.py`/`app.py` despacham pelo registry; executor de turno unificado.
- +13 testes (`tests/test_heroes.py`) e `scripts/sim_enigma_vs_bravo.py`.
