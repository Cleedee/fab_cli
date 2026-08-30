# flesh-and-blood

Assistente de decisão para **Flesh and Blood TCG** — formato **Silver Age**.
Matchup inicial: **Briar, Warden of Thorns** vs. **Enigma** (ambos jovens, 20 vida / 4 intelecto).

> ⚠️ Não é um simulador de regras completo. O foco é **apoio à decisão**:
> matemática de combate, sugestões de defesa/ataque, probabilidades e revisão pós-jogo.
> O usuário controla os **dois lados** da mesa e declara manualmente o estado.

> ⚠️ Projecto não comercial e **não afiliado à Legend Story Studios**.
> Flesh and Blood™, Legend Story Studios® e nomes de produtos são marcas
> registradas da Legend Story Studios. Cartas, personagens e artes pertencem
> à Legend Story Studios.

## Instalação

```bash
git clone <url-do-repositorio>
cd flesh-and-blood
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

Para usar apenas o motor (sem TUI), as dependências mínimas são Python 3.11+ e PyYAML.

A TUI (Textual) é instalada automaticamente com o pacote.

## Dados e licenças

Por razões de licença, os seguintes arquivos **não estão no repositório** e
devem ser gerados localmente:

| Arquivo | Fonte | Motivo |
|---|---|---|
| `data/cards.yaml` | dataset `the-fab-cube/flesh-and-blood-cards` | sem licença formal no dataset |
| `data/decks/*.yaml` | decklists de `fabtcg.com` | ToS do site proíbe redistribuição sem consentimento |

O código-fonte (em `src/`, `tests/`, `scripts/`) é autoral e fica fora dessa
restrição. Gere os dados assim:

```bash
# 1. Registro de cartas (data/cards.yaml)
#    Baixe o json.zip da release mais recente de
#    https://github.com/the-fab-cube/flesh-and-blood-cards
python scripts/build_cards.py --dataset-dir <caminho>/json/english

# 2. Decklists (data/decks/*.yaml) — como descrito abaixo
python scripts/fetch_decklist.py <url-do-fabtcg>
```

Sem o `data/cards.yaml` o `fab` não inicia; sem as decklists, use
`--deck-a`/`--deck-b` apontando para decklists próprias no formato de
`data/decks/`.

## Uso

```bash
# Iniciar a interface TUI (padrão: Briar vs Enigma)
fab

# Escolher decks arbitrários (decklists YAML em data/decks/)
fab --deck-a data/decks/enigma_sa.yaml --deck-b data/decks/briar_sa.yaml

# Escolher quem começa
fab --first B

# Ajuda da CLI
fab --help
```

Os `--deck-a`/`--deck-b` aceitam qualquer decklist Silver Age em YAML com o
formato de `data/decks/` (campos `hero`, `arena`, `deck_pool`). O herói,
a arma e os labels da TUI são derivados automaticamente da decklist; heróis
novos usam os types do registro de cartas para validar o card-pool.

```bash
# Setup automático: mão inicial de 4 cartas sorteadas + equipamentos da arena
fab --auto-setup

# Reproduzir a mesma mão de uma partida anterior (seed)
fab --auto-setup --seed 42

# Setup a partir de arquivo JSON/YAML (mãos, arsenal, equipamentos, pitch_pool)
fab --setup meu_estado.json --deck-a data/decks/enigma_sa.yaml
```

Com `--auto-setup` o pool é **expandido por quantidade** (ex.: 2 cópias
entram 2x no sorteio) e as mãos são sorteadas com a semente indicada.
Sem `--seed`, cada execução gera mãos diferentes; com `--seed 42`, a
mesma semente produz exatamente as mesmas mãos.

O formato do arquivo de setup (JSON ou YAML):

```json
{
  "hands":     {"A": ["Snatch (red)", "Sizzle (red)"], "B": ["Unmovable (blue)"]},
  "arsenal":   {"A": "Arcanic Shockwave (red)", "B": null},
  "equipment": {"A": ["Blade Beckoner Helm"], "B": ["Silent Stilettos"]},
  "pitch_pool": {"A": 1, "B": 0},
  "weapons":   {"A": "Star Fall"}
}
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

Opcional `from=graveyard` em `play`/`attack` joga a carta do cemitério — a passiva
do **Gravy Bones** (card blue entrando no cemitério neste turno habilita jogar
cards com *watery grave* de lá) é validada automaticamente.
Exemplo: `play "Angry Bones (blue)" from=graveyard`

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
| `life <±N> [a\|b]` | Ajusta vida manualmente fora de combate (negativo tira, positivo soma). Lado opcional, default o ativo |

Exemplo: `resolve ward=3 arcane=2` · `life -4` (tira 4 do ativo) · `life b +2` (soma 2 ao lado B)

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
| `board [filtros]` | Abre uma janela modal com as cartas em jogo e nas mãos. Filtros combináveis: `hand`, `field`, `a`, `b`. Navegar com ↑/↓, fechar com Esc ou `q` |
| `read [carta\|N]` | Abre uma janela modal de detalhes. Sem argumento abre o board; `<carta>` busca no registro; `<N>` é a carta N da mão do ativo |
| `card <carta\|número>` | Mostra detalhes completos de uma carta no log (custo, poder, texto, keywords) |
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
src/flesh_and_blood/
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
├── cards.yaml           — registro de cartas (gerado localmente, fora do git)
└── decks/
    ├── briar_sa.yaml    — deck Briar Silver Age (gerado, fora do git)
    └── enigma_sa.yaml   — deck Enigma Silver Age (gerado, fora do git)
tests/                   — ~200 testes (pytest)
```

## Importar decklists da internet

O script `scripts/fetch_decklist.py` baixa uma decklist do site oficial
(fabtcg.com/decklists/) e converte para o formato YAML do projeto:

```bash
# baixa e salva em data/decks/<slug>.yaml
python scripts/fetch_decklist.py \
  https://fabtcg.com/decklists/richard-gillingham-enigma-eternal-weekend-blitz-championship/

# escolher o arquivo de saída
python scripts/fetch_decklist.py <url> --out data/decks/minha_lista.yaml

# também aceita arquivo HTML local (para debug)
python scripts/fetch_decklist.py /caminho/pagina.html --out data/decks/teste.yaml
```

Depois de importar, use com a CLI:

```bash
fab --deck-a data/decks/minha_lista.yaml
```

> ⚠️ O registro `data/cards.yaml` (gerado localmente — veja "Dados e licenças")
> precisa cobrir as cartas da decklist importada. Para jogar decklists com
> cartas fora do matchup padrão, rode antes `scripts/build_cards.py` com o
> dataset completo (veja AGENTS.md).

## Desenvolvimento

```bash
# testes
python3 -m pytest -q

# lint + formatação
ruff format src tests scripts && ruff check src tests scripts
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