# Plano de matchup — Enigma (Colin Li) vs Dromai (Silver Age)

- Deck Enigma: `data/decks/enigma_colin_li.yaml`
- Deck Dromai: `data/decks/01M1AXGQHEVNKV5R7NHYARTGS6.yaml`
  (baixado de `https://fabrary.net/decks/01M1AXGQHEVNKV5R7NHYARTGS6`)
- Ambos validados pelo `deck.validate` do repo (pool de 55, 0 erros).

## Regras-base que decidem o matchup

Fontes: Comprehensive Rules 8.2.8 e 8.3.13 (Phantasm).

- **Alas (allies) podem ser atacadas** e **não podem ser defendidas** pelo controlador
  (CR 8.2.8d: não se declara bloqueio para elas).
- **A vida da ala reseta no End Phase** (CR 8.2.8b). Logo, dano fatiado em dragão é
  **desperdiçado**: é preciso matá-la **no mesmo turno**.
- **Todos os dragões da Dromai têm Phantasm** (confirmado pelo texto do `Miragai`).
  Mas atenção à condição exata (CR 8.3.13): o Phantasm só dispara quando o dragão é
  **defendido por uma carta de ataque (attack action) NÃO-Illusionist com 6+ de poder**.
  → Os atacantes grandes do Enigma (`Clear Conscience`, `Enigma Chimera`) são
  **Illusionist** e portanto **NÃO popam dragões**. O plano antigo de "popar na defesa"
  está **errado** (ver seção de remoção).
- Cartas que dizem "target hero" **não** podem mirar alas (e vice-versa).

## Leitura do matchup

- **A Dromai é o beatdown.** Ela quer montar 2–4 dragões e atacar com todos num turno
  (o herói dá Go Again quando ela joga uma vermelha). Se a mesa dela crescer, ela
  enterra a Enigma em valor.
- **A Enigma é o controle/atrito.** As auras com Ward são as armas (Cosmo) e, sobretudo,
  **sobrevivem** — a Dromai não tem remoção de aura. O dano é recorrente; a Enigma ganha
  a corrida longa **matando os dragões em combate direto** e bloqueando bem.
- Diferença crucial após a correção: a Enigma **não tem como popar dragões de graça**
  na defesa. A remoção é **proativa** (atacar as alas no seu turno). Isso valoriza a
  defesa eficiente para **chegar viva ao seu turno** e o motor de auras para matar alas
  **de uma vez**.

## Ferramentas de remoção da Enigma (plano central — corrigido)

### 1. Matar a ala atacando direto (plano principal)

A ala **não pode ser defendida**; qualquer ataque que iguale a vida a mata, desde que
**no mesmo turno** (a vida reseta no End Phase).

| Dragão | Poder | Vida | Observação |
|---|---|---|---|
| `Cromai` | 3 | 2 | Dá AP mesmo ao sair/atacar → mate-o **no seu turno** (não "popa" por AP). |
| `Kyloria` | 4 | 2 | Rouba item / compra → priorizar. |
| `Azvolai` | 2 | 3 | 1 dano arcano em até 2 alvos a cada ataque. |
| `Miragai` | 2 | 4 | 1º ataque de dragão do turno dela perde Phantasm. |
| `Themai` | 3 | 4 | Trava jogar cartas/ativar habilidades. |
| `Ouvia` | 1 | 6 | Tanque; só com burst/múltiplos ataques. |
| `Yendurai` | 3 | 3 | Endurance counter previne 3 de dano. |

Fontes dos stats: `card.json` (the-fab-cube). Ataques de aura via Cosmo (3–7) também
matam alas. Prioridade: `Cromai`/`Kyloria` (baratos, alto valor).

### 2. "Popar" na defesa (praticamente inexistente neste deck)

Só dispara Phantasm quem defende com **attack action não-Illusionist 6+**. Os atacantes
de 6+ do Enigma são Illusionist → **não popam**:

- `Clear Conscience (red)` 8 / `(blue)` 6 — **Illusionist**, não popa.
- `Enigma Chimera` 6/8 — **Illusionist**, não popa.
- `Spears of Surreality` — **Illusionist**, não popa.

Única exceção teórica: **`Second Tenet of Chi: Tide/Wind`** é **Mystic** (não-Illusionist),
5 de base, **7 se transcender** no turno → **pode popar** um dragão na defesa. É nicho e
exige ter transcendido; não conte com isso como plano.

### 3. O Phantasm da Enigma é seguro

`Enigma Chimera`/`Spears of Surreality` têm Phantasm, mas **a Dromai não tem ataque de
6+ de poder** (teto: `Ravenous Rabble`/`Dunebreaker Cenipai` = 5; `Haboob` só reduz).
Ela **não consegue popar você**.

## Plano por fase

- **Early (ela monta ash):** monte 1–2 auras (`Solitary Companion`,
  `Spectral Manifestations`) e **guarde um 5+/**burst para matar dragão no seu turno.
  Bloqueie o ataque de ação normal (não-dragão) com parcimônia.
- **Mid:** no seu turno, **mate a ala de maior valor** (Cromai/Kyloria/Themai) com
  ataque de mão ou de aura (Cosmo). Não fatiar: matar **de uma vez**. Se não conseguir
  matar nenhuma, pressione a vida, mas priorize limpar a mesa dela.
- **Late:** a Enigma tem dano recorrente e a Dromai tem pouca ficha (tudo pitch 1). Se a
  troca for 1 carta por 1 dragão, ela **fatiga**. Não deixe auras paradas — ataque com
  elas todo turno.

## Ameaças específicas da Dromai (deste deck)

| Carta | O que faz | Como a Enigma lida |
|---|---|---|
| `Themai` (P3/V4) | Oponente **não pode jogar cartas nem ativar habilidades** no turno dele | Bloqueio com cartas **continua** (não é "jogar"), mas perde `Springboard`/`Big Blue Sky`/`Moon Chakra`/`Oasis Respite`. **Mate o Themai no seu turno**. |
| `Haboob` | Ataques-carta ganham **‑1{p}** | Afeta sua remoção por ataque; **dano de aura (Cosmo) não é afetado** → prefira matar alas com auras. Enigma não tem remoção de aura: engula o `Haboob`. |
| `Miragai` (P2/V4) | O **primeiro** ataque de dragão do turno dela perde Phantasm | Relevante só para o pop via `Second Tenet`; no plano de ataque direto, mate como qualquer ala (4 de vida). |
| `Cromai` (P3/V2) | Ganha AP ao atacar ou sair | Mate no seu turno; ele já deu o AP no turno dela. |
| `Kyloria` (P4/V2) | Rouba item / compra carta | Alto valor: priorize matar. |
| `Azvolai` (P2/V3) | 1 dano **arcano** em até 2 alvos por ataque | Dano arcano não é bloqueável; `Silent Stilettos` (Arcane Barrier 1) / `Moon Chakra` / `Oasis Respite`. |
| `Yendurai` (P3/V3) | Endurance counter previne 3 de dano | Não fatiar: ou burst ≥ 6 no turno, ou ignore. |

## Mão inicial, arsenal e equipamento

### Mão inicial (não existe mulligan no FAB)

No Flesh and Blood **não há mulligan**: você compra a mão inicial e joga com o que veio —
o plano se adapta à mão, não o contrário. Numa abertura boa, busque:

- **1 motor de aura** (`Solitary Companion`, `Spectral Manifestations`, ou a própria
  habilidade do herói);
- **1 burst/ataque para matar ala** (`Clear Conscience`, `Enigma Chimera`, `Second Tenet`);
- **1 azul** para recursos;
- **1 carta de bloqueio/prevenção** (`Springboard`, `Big Blue Sky`, `Sink Below`).

Mão ruim (só auras caras, sem ataque/AZUL): não force o Cosmo. Use o turno para
desenvolver, defender e estabilizar; o motor de auras não precisa atacar todo turno.

### Arsenal

No fim do turno você pode guardar **1 carta** virada para baixo. Como a remoção agora é
**proativa**, o arsenal serve para guardar a **próxima carta que mata ala** (ex.: um
ataque/AZUL do motor) — o `Second Tenet` também fica ótimo se você planeja transcender.

### Equipamento (1 por slot)

- **Cabeça / peito:** `Blade Beckoner Helm` + `Blade Beckoner Plating` (defesa 1 — o
  enxame dela é físico).
- **Braços:** `Uphold Tradition` (Ward 1 + contador instantâneo → liga o Go Again das
  auras).
- **Pernas:** `Silent Stilettos` (Arcane Barrier 1 contra o `Azvolai`).
- `Unflinching Foothold` é inútil aqui (a Dromai não tem Dominate); `Nullrune` só vale se
  temer muito o `Azvolai` — cada peça tem 0 de defesa, então não exagere.

## Erros que perdem o jogo

1. **Acreditar que "poppa" dragão defendendo com `Clear Conscience`/`Enigma Chimera`**:
   são Illusionist, não disparam Phantasm. Remoção é **no seu turno, atacando a ala**.
2. **Fatiar dano em dragão** — a vida reseta no End Phase; mate no mesmo turno.
3. Gastar recursos/cartas de motor para bloquear dragões pequenos e chegar sem plano
   ao seu turno. Bloqueie o essencial para sobreviver; o motor reconstroi.
4. Ignorar `Themai` e ser travado sem carta reativa no turno decisivo.

**Resumo:** jogue de controle — bloqueie eficientemente, mate os dragões **atacando-os
diretamente** (matando no mesmo turno), grind com auras do Cosmo e deixe a Dromai
fatigar. Não existe atalho de Phantasm para o Enigma.
