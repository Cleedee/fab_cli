# fresh-and-blood

Assistente de decisão para **Flesh and Blood TCG** — formato **Silver Age**.
Matchup inicial: **Briar, Warden of Thorns** vs. **Enigma** (ambos jovens, 20 vida / 4 intelecto).

> ⚠️ Não é um simulador de regras completo. O foco é **apoio à decisão**:
> matemática de combate, sugestões de defesa/ataque, probabilidades e revisão pós-jogo.
> O usuário controla os **dois lados** da mesa e declara manualmente o estado.

## Instalação

```bash
git clone <url-do-repositorio>
cd fresh-and-blood
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

Para usar apenas o motor (sem TUI), as dependências mínimas são Python 3.11+ e PyYAML.

A TUI (Textual) é instalada automaticamente com o pacote.

## Uso

```bash
# Iniciar a interface TUI
fab
```

### Atalhos de teclado

| Tecla | Ação |
|---|---|
| `F1` | Ajuda (lista de comandos) |
| `F5` | Sugerir defesa (para o defensor) |
| `F6` | Planejar ataque (para o atacante) |
| `Tab` | Trocar lado ativo |
| `Ctrl+Q` | Sair |

### Comandos

Digite no campo de texto inferior e pressione Enter.

#### Gerenciamento de mão

| Comando | Descrição |
|---|---|
| `draw <carta>` | Adiciona carta à mão do jogador ativo |
| `pitch <carta>` | Dá pitch de uma carta da mão (gera recursos) |
| `arsenal <carta>` | Coloca uma carta da mão no arsenal |

Cartas podem ser referidas por nome parcial (`Snatch`, `Arcanic Shock`) ou pelo
número na lista da mão (`1`, `2`, etc.).

#### Jogar cartas e atacar

| Comando | Descrição |
|---|---|
| `play <carta>` | Joga uma non-attack action (buffs, Sizzle, etc.) |
| `attack <carta>` | Declara ataque com uma attack action da mão |
| `weapon` | Ataca com a arma do herói (Star Fall / Cosmo) |
| `boost <N>` | Adiciona +N{p} ao chain link ativo |
| `arcane <N>` | Adiciona +N de dano arcano ao chain link ativo |

Para ataques com Dominate: `attack Snatch dominate=1`

#### Defesa

| Comando | Descrição |
|---|---|
| `defend <carta> [carta ...]` | Bloqueia com uma ou mais cartas da mão |
| `equip <nome>` | Usa um equipamento para defender (uma vez por turno) |

Armas e cartas com `"Action"` no tipo contam para o limite do Dominate
(máx. 2 cartas, sendo no máximo 1 action card).

#### Resolução

| Comando | Descrição |
|---|---|
| `resolve [ward=N] [arcane=N]` | Resolve o chain link ativo. Opcionalmente informa quanto dano foi prevenido por Ward ou Arcane Barrier |

Exemplo: `resolve ward=3 arcane=2`

#### Turno

| Comando | Descrição |
|---|---|
| `next` | Encerra o turno do jogador ativo e inicia o do oponente |
| `switch` | Troca manualmente o lado ativo |

#### Sugestões

| Comando | Descrição |
|---|---|
| `plan` | Sugere linha de ataque para o jogador ativo (sequência, dano, lethal) |
| `suggest` | Sugere top-3 opções de defesa para o defensor |
| `prob <copias> <deck> <compras> [min=1]` | Calcula probabilidade hipergeométrica |

Exemplo: `prob 3 40 7` → chance de comprar ao menos 1 das 3 cópias em 7 compras de um deck de 40.

#### Log e revisão pós-jogo

| Comando | Descrição |
|---|---|
| `log` | Exibe o histórico completo da sessão atual |
| `save [nome]` | Salva o log em `data/logs/<nome>.json` |
| `load [nome]` | Carrega um log salvo anteriormente |
| `review` | Visão geral do replay da sessão atual |
| `metrics` | Estatísticas da sessão (dano por lado, ataques, defesas) |

#### Utilitários

| Comando | Descrição |
|---|---|
| `status` | Log completo do estado dos dois jogadores e chain |
| `clear` | Limpa a área de notificações |
| `undo` | Desfaz a última ação que alterou o estado |
| `reset` | Reinicia a partida do zero (limpa todo o estado) |
| `help` | Lista completa de comandos |

### Exemplo de sessão

```
# Turno 1 — Briar (A)
help                            → mostra os comandos

# Briar compra mão inicial
draw "Snatch (red)"             → Briar compra Snatch
draw "Sizzle (red)"             → Briar compra Sizzle (buff)
draw "Sigil of Suffering (red)" → Briar compra Sigil (DR)
draw "Arcanic Shockwave (red)"  → Briar compra Shockwave

# Enigma (B) também precisa de cartas para defender
switch                          → troca para lado B
draw "Unmovable (blue)"         → Enigma compra Unmovable (DR, def 5)
draw "Sizzle (red)"             → Enigma compra Sizzle (ação, def 2)
switch                          → volta para lado A

# Pitch + ataque
pitch "Sigil of Suffering (red)" → +1{r} no pool
attack "Snatch (red)"           → declara ataque 4{p}

# Enigma (B) defende
defend 1                        → descarta 1ª carta (Unmovable, def 5)
resolve                         → aplica dano: 0 (bloqueio cobre tudo)

# Briar ataca com a arma
weapon                          → Star Fall +1{p}
resolve                         → resolve dano da arma
next                            → encerra turno 1, inicia turno 2

# Turno 2 — Enigma (B)
draw "Look Tuff (red)"          → Enigma compra Look Tuff
plan                            → sugere linha de ataque

# Salvar sessão
save "partida1"                 → salva em data/logs/partida1.json
metrics                         → estatísticas da sessão
log                             → histórico completo
```

## Projeto

```
src/fresh_and_blood/
├── __init__.py          — versão do pacote
├── app.py               — TUI Textual (Fase 3)
├── attack.py            — planejador de linha de ataque (Fase 2)
├── carddb.py            — carga do registro de cartas (Fase 0)
├── cli.py               — ponto de entrada (fab)
├── combat.py            — motor de combate (Fase 1)
├── deck.py              — validação de decks Silver Age (Fase 0)
├── defense.py           — sugeridor de defesa (Fase 2)
├── models.py            — modelos de dados (Fase 0)
├── probabilities.py     — probabilidades hipergeométricas (Fase 2)
├── recorder.py          — log de sessão (Fase 4)
└── review.py            — métricas e revisão pós-jogo (Fase 4)
data/
├── cards.yaml           — registro de cartas (gerado)
└── decks/
    ├── briar_sa.yaml    — deck Briar Silver Age
    └── enigma_sa.yaml   — deck Enigma Silver Age
tests/                   — 80 testes (pytest)
```

## Desenvolvimento

```bash
# testes
python3 -m pytest -q

# lint + formatação
ruff format src tests && ruff check src tests
```

## Regras do formato Silver Age (TRP 7.4)

- Herói jovem; pool de **55 cartas** (armas + equipamentos + deck); **40 apresentadas** por partida
- Máximo **2 cópias** por carta única (nome + cor)
- Apenas raridades common, rare e basic
- Bans relevantes do matchup: Burn Up // Shock, Lightning Press, Bracers of Belief,
  Beckoning Haunt, Flourish, Sink Below, Fate Foreseen, etc.
  (lista completa: [fabtcg.com → Card Legality Policy](https://fabtcg.com))

### Heróis

**Briar, Warden of Thorns** (Elemental Runeblade — 20 vida, 4 intelecto)
- 1ª vez que uma attack action sua causa dano → cria **Embodiment of Earth** (non-attack actions defendem com +1{d})
- 2ª non-attack action do turno → cria **Embodiment of Lightning** (próximo ataque ganha Go Again)
- Arma Star Fall não conta como attack action para Embodiment of Earth

**Enigma** (Mystic Illusionist — 20 vida, 4 intelecto)
- Passiva: primeiro ataque de Spectral Shield por turno custa {r} a menos
- Ativa (once per turn): cria token **Spectral Shield** com contador +1
- Cosmo ataca usando uma aura com ward (dano = ward + contadores)