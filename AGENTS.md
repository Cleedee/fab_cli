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
| `models.py` | `Card`, `Hero`, `PlayerState`, `ChainLink`, `GameState`, save/load JSON; prioridade/reactions (`priority`, `passes`, `ChainLink.responses`); `PlayerState.deck` (topo = índice 0) |
| `carddb.py` | carrega `data/cards.yaml` |
| `deck.py` | decklists YAML + validação Silver Age (pool=55, ≤2 cópias, classes do herói) |
| `combat.py` | operações de turno/combate; prioridade (`give_priority`/`pass_priority`), `play_reaction`, `draw_from_deck`; valida e devolve `Notice`s (triggers manuais) |
| `attack.py` | planejadores de turno: `plan_attack` (burst/lethal) e `plan_enigma` (Cosmo/auras) |
| `defense.py` | sugeridor de defesa (usado pelo bot na defesa) |
| `bot.py` | política automática: executa `plan_enigma`, defesa via `suggest_defense` |
| `setup.py` | auto_setup (monta mão inicial, arsenal e `PlayerState.deck` restante) |
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
- Corrente/cemitério: toda carta jogada vai à corrente — a attack action cria
  um elo; uma non-attack action quebra a corrente de combate em andamento
  (seus elos abertos fecham: cartas de ataque/defesa vão aos cemitérios,
  armas/equipamentos permanecem equipados) e abre um elo próprio. `resolve`
  move as cartas do elo ao cemitério do atacante; permanentes ficam em jogo e
  armas permanecem equipadas. Cards blue que entram no cemitério ao quebrar a
  corrente alimentam a passiva watery grave (`_close_combat_chain`).
- Dano físico é bloqueado por defesa das cartas; **dano arcano não é bloqueável**
  (prevenção manual: Arcane Barrier/spellvoid entram como parâmetro `*_prevented`).
- Dominate: defensor usa no máximo 2 cartas, sendo no máximo 1 action card.
- Watery grave (Gravy Bones): `discard` de um card blue no turno seta
  `blue_to_graveyard_this_turn` (reset no `start_turn`); `play`/`attack` aceitam
  `from=graveyard` validando a passiva (herói Gravy Bones + blue no turno +
  carta com watery grave — detectado no texto, pois o dataset não tem keyword).
- Permanentes (Ally/Item/Landmark): `play`/`token` colocam a carta em
  `permanents` (zona própria no painel/board/status — não some da mesa);
  `token remove` destrói. Nomes resolvem por parcial (`play "Riggermortis"`).
- Comando `life <±N> [a|b]`: ajuste manual de vida fora de combate.
- Motor Enigma (Coso/auras) em `combat.py`:
  - `activate_hero_ability`: once per turn instant da Enigma (3 recursos, cria
    Spectral Shield +1), marca `hero_ability_used`; não gasta AP (é instant).
  - `attack_with_aura`: Cosmo ataca com aura ward (p = ward base + contadores;
    custo 1, 1º Spectral Shield do turno custa 0; Go Again se a cópia tem
    contadores; once per turn por aura). A aura NUNCA sai de jogo ao atacar
    (não entra em `played`). Contagem em `spectral_attacks_this_turn`.
  - `play_aura_engine` (motor: Spectral Manifestations cria shield +3; Solitary
    Companion vira aura Ward 3 + shield) e `play_instant_aura` (instants não
    gastam AP: auras entram na mesa, transcend/proteções vão ao cemitério —
    nada disso cria/quebra elo). `astral_charge` dá +3 contadores (instant se
    controla Spectral Shield).
- Bot (`bot.py`): `run_bot_turn` executa `plan_enigma`/`plan_attack` passo a
  passo resolvendo cada elo NA HORA (MVP assume oponente sem bloqueio — ajuste
  manual com `life`) e termina passando a prioridade (`pass_priority`);
  `choose_bot_defense` usa `suggest_defense`. No app, comando
  `bot <a|b|off|turn|defend>` ativa o lado e o `next` executa o turno do bot.
- Prioridade (`combat.py`): `GameState.priority` (None antes de começar) e
  `GameState.passes`; `new_game` seta para `first_player`, `start_turn` para o
  lado ativo com `passes=0`. `pass_priority` passa a palavra ao oponente; 2
  passes consecutivos com elo aberto → `resolve_link` no topo (dano físico
  aplicado ao defensor) e a palavra volta ao jogador ativo. Agir fora da
  prioridade gera AVISO amarelo (apoio, não bloqueio). `play_reaction` registra
  reactions/instants no `ChainLink.responses`: defense reactions bloqueiam
  (+1{d} Embodiment of Earth se non-attack action), attack reactions somam
  power, instants/aura-instants delegam a `play_instant_aura`; sempre sem AP e
  sem quebrar a corrente. Reactions: exige ter a carta na mão e recursos.
- Draw do deck: `PlayerState.deck` (topo = índice 0) é o restante do pool de
  deck após o `auto_setup` da mão; `draw` sem args em `app.py` compra do topo
  (`draw_from_deck`), `draw <carta>` continua manual (registro de partidas do
  YouTube); comando `deck <a|b> <arquivo>` monta/embaralha o pool de decklists
  de `data/decks/`.

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
- [x] Fase 5b — bot Enigma: motor Cosmo/auras (260 testes), `plan_enigma`
      (`attack.py`), `bot.py` (turno + defesa), comando `bot` e auto-turno no `next`
- [x] Fase 5c — prioridade/reactions formais + draw do deck (279 testes):
      `GameState.priority`/`passes`, `pass` (2 passes → auto-resolve do topo),
      `react` (DR/AR/instants em `ChainLink.responses`, sem AP, sem quebrar
      corrente), AVISO fora da prioridade, `draw` regrado (topo de
      `PlayerState.deck`), comando `deck <a|b> <arquivo>`, save/load preserva
      prioridade
