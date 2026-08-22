# FaB Decision Assistant — Plano de Desenvolvimento

## Visão geral

Ferramenta em **terminal (TUI)** para simular partidas de **Classic Constructed** de Flesh and Blood,
com o usuário controlando os dois lados. O foco não é validar regras automaticamente, mas sim
**apoiar decisões**: matemática correta de combate, sugestões de defesa/ataque, probabilidades
e revisão pós-jogo.

O jogador entra manualmente com o estado da mesa (mão, vida, recursos, chain); o assistente
cuida dos números difíceis e das escolhas ótimas.

## Stack

| Camada | Escolha | Motivo |
|---|---|---|
| Linguagem | Python 3.11+ | Ecossistema maduro, tipagem com `typing` |
| TUI | [Textual](https://textual.textualize.io/) | Framework moderno, widgets prontos, inclui Rich |
| Modelos | `dataclasses` + validação leve | Simples; Pydantic só se crescer |
| Dados de cartas | YAML curado (decklists dos seus heróis) | Começar pequeno; integrar API/dataset depois |
| Testes | pytest | Padrão |
| Lint/format | ruff | Rápido, cobre tudo |

## Fases

### Fase 0 — Fundação
- Estrutura de pacote (`src/fab_assistant/`), `pyproject.toml`, ruff, pytest.
- Modelo `Card`: nome, tipo, custo, attack, defense, pitch, keywords (`go again`,
  `dominate`, ...), efeitos como texto estruturado mínimo.
- Modelo `GameState`: 2 heróis (vida, mão, arsenal, graveyard, banished, pitch/recursos),
  chain links ativos, jogador ativo, turno.
- Save/load do estado em JSON (partidas pausáveis).
- Decklists iniciais em YAML: **definir o primeiro matchup** (seus 2 heróis principais).

### Fase 1 — Matemática de combate (núcleo, sem TUI)
- Calculadora de chain link: dano declarado − bloqueio = dano final.
- Múltiplos ataques por turno (action points), rastreio de Go Again.
- Recursos: pitch → custo, sobra vira recurso.
- Equipamentos: uso once-per-turn, contagem de usos.
- **Lethal checker**: dado o estado, existe linha de ataque letal neste turno?
- Testes unitários cobrindo todos os cálculos.

### Fase 2 — Motor de decisão
- **Sugeridor de defesa**: dado(s) ataque(s) recebidos e sua mão, propõe o conjunto de
  bloqueios que minimiza dano sofrido preservando valor de mão (pitch/utility ponderado).
- **Planejador de ataque**: ordena ataques da mão maximizando dano total considerando
  custos, Go Again e equipamentos.
- **Probabilidades**: hipergeométrica (chance de comprar X cópias nas próximas N cartas),
  chance de acertar cores de pitch.
- **Checklist de triggers**: lembretes de on-hit/on-block das cartas envolvidas no link.

### Fase 3 — Interface TUI (Textual)
- Tela de mesa: dois painéis lado a lado (heróis) com vida, mão, recursos, arsenal.
- Fluxo guiado: atacante declara → defensor bloqueia (com sugestão visível) → resolve.
- Comandos rápidos: adicionar/remover carta da mão, pôr no arsenal, avançar turno,
  desfazer última ação.
- Atalhos de teclado para tudo (jogo fluido no terminal).

### Fase 4 — Aprendizado
- Log de cada ponto de decisão com snapshot completo do estado.
- **Review pós-jogo**: replay das decisões mostrando alternativas e o resultado esperado.
- Métricas por sessão: dano sofrido por turno, dano por carta jogada, taxa de lethal perdido.
- Notas de matchup anexadas aos saves.

## MVP (marco da primeira versão utilizável)

Um confronto entre dois decks CC conhecidos:
1. Estado manual via comandos de terminal;
2. Calculadora de dano de chain link;
3. Sugestão de defesa ótima;
4. Lethal checker;
5. Chance de compra (hipergeométrica).

Tudo isso já cabe na CLI antes da TUI bonita — a TUI (Fase 3) vem depois do motor estar sólido.

## Matchup inicial (decidido)

**Briar, Warden of Thorns vs. Enigma — Silver Age**

Regras do formato que o motor precisa conhecer (TRP 7.4):
- 1 herói jovem; pool de **55 cartas** (armas + equipamentos + deck); **40 apresentadas** por partida.
- Máx. **2 cópias** por carta única (nome+cor); só raridades common/rare/basic.
- Bans relevantes ao matchup (vigência 03/03/2026): Burn Up // Shock, Lightning Press,
  Bracers of Belief, Beckoning Haunt, Flourish, Sink Below, Fate Foreseen, Rosetta Thorn,
  Sigil of Solace, Zephyr Needle etc. (lista completa: Card Legality Policy).
- Heróis: Briar jovem = Elemental Runeblade, **20 vida / 4 intelecto**, Essence of Earth and
  Lightning (errata: *primeira* vez que attack action causa dano → Embodiment of Earth;
  *segunda* non-attack action → Embodiment of Lightning). Enigma jovem = Mystic Illusionist,
  **20 vida / 4 intelecto**, primeiro ataque de Spectral Shield por turno custa 1 a menos;
  ability ativa: cria Spectral Shield token com contador +1.

## Fonte de dados

Registro de cartas gerado a partir do dataset comunitário
[the-fab-cube/flesh-and-blood-cards](https://github.com/the-fab-cube/flesh-and-blood-cards):

```bash
# baixe json.zip da release mais recente e rode:
python scripts/build_cards.py --dataset-dir /caminho/json/english
```

Gera `data/cards.yaml` (67 cartas do matchup + tokens). Overrides manuais para limitações
do dataset ficam em `OVERRIDES` no script (ex.: Briar jovem é dupla-face com a adulta).

Decklists em `data/decks/`: `enigma_sa.yaml` (pré-construído oficial Chapter 2) e
`briar_sa.yaml` (lista do Spotlight de fev/2026 adaptada aos bans de mar/2026).

## Status

- [x] Fase 0 — fundação: modelos (`models.py`), registro de cartas (`carddb.py`),
      carga/validação de decks Silver Age (`deck.py`), decklists dos dois heróis, testes.
- [x] Fase 1 — matemática de combate (`combat.py`, 48 testes):
      turnos com reset de contadores por turno; pitch/recursos com custo;
      play_action (AP: gasta 1, Go Again devolve; Defense Reaction bloqueada);
      declare_attack (mão/arsenal/arma once-per-turn, Embodiment of Lightning
      consumido automaticamente para Go Again); boosts e arcano por link;
      defesa (Embodiment of Earth dá +1{d} a non-attack actions; Dominate:
      máx. 2 cartas sendo 1 action); equipamentos once-per-turn;
      ward (Spectral Shield com contadores, maior contador primeiro);
      resolução (físico + arcano separados, Arcane Barrier manual via parâmetro);
      triggers da Briar (Earth na 1ª vez que attack action causa dano — arma não conta;
      Lightning na 2ª non-attack action).
- [x] Fase 2 — sugestões de defesa/ataque + probabilidades (67 testes):
      `probabilities.py` (hipergeométrica exata: compra e pitch);
      `defense.py` (enumeração de subsets, heurística de valor configurável,
      Dominate, equipamentos como bloqueio sem custo de mão);
      `attack.py` (planejador em 3 fases com fusão, Embodiment of Lightning,
      arma condicional e corte de menor ataque para virar pitch).
- [ ] Fase 3 — TUI (Textual).
- [ ] Fase 4 — log de decisões e review pós-jogo.

## Decisões abertas

- [ ] Efeitos complexos: manter como texto + checklist manual; codificar quando afetarem matemática.
