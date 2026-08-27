# AGENTS.md

Diretrizes para agentes de código (e humanos) trabalhando neste repositório.
Leia antes de qualquer alteração — evita re-pesquisar o domínio a cada sessão.

## Projeto

Assistente de decisão para **Flesh and Blood TCG**, formato **Silver Age**, matchup
inicial **Briar, Warden of Thorns vs. Enigma** (ambas jovens, 20 vida / 4 intelecto).
O usuário controla os DOIS lados da mesa. Filosofia: apoio à decisão (matemática,
sugestões, probabilidades, lembretes de trigger) — NÃO é um validador completo de regras.

## Comandos

```bash
# setup
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'

# testes (rodar SEMPRE antes de commitar)
.venv/bin/python -m pytest -q

# lint + format
.venv/bin/ruff format src tests scripts && .venv/bin/ruff check src tests scripts

# regenerar data/cards.yaml (registro gerado, não editar à mão):
# baixe json.zip da release mais recente de
# https://github.com/the-fab-cube/flesh-and-blood-cards
python scripts/build_cards.py --dataset-dir <caminho>/json/english

# ATENÇÃO — dados fora do git (questões de licença):
# data/cards.yaml (dataset sem licença formal) e data/decks/*.yaml
# (decklists de fabtcg.com, ToS proíbe redistribuição) são .gitignored.
# O código-fonte DEVE funcionar com esses arquivos presentes localmente;
# na ausência deles, a CI/commit verifica com --skip-dados (ver abaixo).
```

## Dados e testes

- `data/cards.yaml` e `data/decks/*.yaml` são **excluídos do git** (ver `.gitignore`).
- Em clone limpo, gere os dados (seção acima) antes de rodar testes —
  as fixtures carregam `load_cards()` e `data/decks/*_sa.yaml`.
- Nunca commitar dados gerados por `build_cards.py` ou `fetch_decklist.py`.

## Arquitetura (`src/flesh_and_blood/`)

| Módulo | Responsabilidade |
|---|---|
| `models.py` | `Card`, `Hero`, `PlayerState`, `ChainLink`, `GameState`, save/load JSON |
| `carddb.py` | carrega `data/cards.yaml` |
| `deck.py` | decklists YAML + validação Silver Age (pool=55, ≤2 cópias, classes do herói) |
| `combat.py` | operações de turno/combate; valida e devolve `Notice`s (triggers manuais) |
| `cli.py` | ponto de entrada (TUI textual) |

Dados: `data/decks/*.yaml` (decklists), `data/cards.yaml` (gerado).
Overrides para limitações do dataset ficam no dict `OVERRIDES` de `scripts/build_cards.py`
(ex.: Briar jovem é dupla-face com a adulta; o dataset perde o subtipo "Young").

Scripts auxiliares:
- `scripts/fetch_decklist.py <url>` — baixa decklist da fabtcg.com e converte
  para o formato YAML de `data/decks/` (normaliza cores `(yel)`/`(blu)`,
  decodifica entidades HTML, soma quantidades `Nx`).
  Aceita URL ou arquivo HTML local.

## Convenções

- Docstrings/comentários em pt-BR; identificadores em inglês; sem emojis.
- Chave única de carta = `"Nome (red)"` / `"Nome (yellow)"` / `"Nome (blue)"`;
  sem cor (equipamento/herói/token) = nome puro. Carta ausente do registro → erro explícito.
- Estado mutável somente via funções de `combat.py` (nunca manipular campos direto na UI).
- Testes usam cartas REAIS dos decks sempre que possível (fixtures em `tests/test_combat.py`).
- Commits pequenos por fase/feature, mensagem em pt-BR, estilo do histórico.
- **NUNCA commitar sem pedido explícito do usuário.**

## Domínio — resumo essencial (não re-pesquisar)

### Formato Silver Age (TRP 7.4)
- 1 herói jovem; pool de **55** cartas (armas + equipamentos + deck); exatamente **40**
  apresentados por partida; máx. **2 cópias** por carta única (nome+cor); só raridades
  common/rare/basic ("ever printed").
- Bans relevantes ao matchup (vigência 03/03/2026): Burn Up // Shock, Lightning Press,
  Bracers of Belief, Beckoning Haunt, Flourish, Sink Below, Fate Foreseen, Rosetta Thorn,
  Sigil of Solace, Zephyr Needle, Count Your Blessings, Nimby etc. (lista completa:
  fabtcg.com → Card Legality Policy). Benched nesta temporada: Ira, Kano, Kayo.

### Briar, Warden of Thorns (Elemental Runeblade)
- Errata: a **1ª vez** que uma attack ACTION que você controla causa dano ao herói oposto
  no turno → cria **Embodiment of Earth** (aura: non-attack actions defendem com +1{d};
  destruída no início da SUA action phase seguinte). A **2ª** non-attack action do turno →
  **Embodiment of Lightning** (quando joga attack action, destrói-a e o ataque ganha Go Again).
- Arma (Star Fall) NÃO conta como attack action para o Embodiment of Earth.
- Fyendal's Spring Tunic é ilegal em SA (só impressões Legendary/Promo).

### Enigma (Mystic Illusionist)
- Passiva: o primeiro ataque de Spectral Shield a cada turno custa {r} menos.
- Ativa (once per turn instant): cria token Spectral Shield com contador +1.
- Cosmo, Scroll of Ancestral Tapestry: ataca USANDO uma aura com ward (dano = ward +
  contadores; custo {r} por ataque).
- Ward: destruir a aura previne dano igual a ward+contadores; tokens somem,
  auras de carta vão ao graveyard. Escolhe-se a cópia de maior contador primeiro.

### Regras mecânicas implementadas em `combat.py`
- Action points: toda action (incl. arma, "Once per Turn Action") gasta 1 AP;
  Go Again devolve. Sem AP, não joga — mesmo com Go Again pendente.
- Dano físico é bloqueado por defesa das cartas; **dano arcano não é bloqueável**
  (prevenção manual: Arcane Barrier/spellvoid entram como parâmetro `*_prevented`).
- Dominate: defensor usa no máximo 2 cartas, sendo no máximo 1 action card.

## Status

- [x] Fase 0 — fundação (modelos, carddb, deck validation, decklists)
- [x] Fase 1 — motor de combate (48 testes)
- [x] Fase 2 — decisões (71 testes): `probabilities.py` (hipergeométrica/pitch),
      `defense.py` (sugeridor de defesa c/ suporte a Embodiment of Earth e
      Dominate corrigido: `"Action" in types` em vez de `is_non_attack_action`),
      `attack.py` (planejador burst/lethal em 3 fases; Look Tuff faz downgrade
      em vez de ser removido quando faltam recursos para o {r} extra;
      limitação: não troca buff jogável por pitch p/ {r} extra)
- [x] Fase 3 — TUI Textual
- [x] Fase 4 — log de decisões + review pós-jogo
