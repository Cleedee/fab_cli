# Plano de matchup — Enigma (Colin Li) vs Boltyn (Silver Age)

- Deck Enigma: `data/decks/enigma_colin_li.yaml`
- Deck Boltyn: `data/decks/boltyn_sa.yaml`
  (precon oficial — `https://fabtcg.com/decklists/silver-age-chapter-3-boltyn`)
- Ambos validados pelo `deck.validate` do repo (pool de 55, 0 erros).

## O que o Boltyn faz (deck)

O precon SA do Boltyn é **aggro físico puro** (não tem dano arcano). Motor:
**charge** (banir 1 carta da mão para a alma como custo adicional ao jogar).

| Peça | Jogo |
|---|---|
| `Valiant Thrust (red)` | 1{r}, 4{p} → **7{p}** se carregou. É o hit mais alto do deck. |
| `V of the Vanguard (yel)` | 1{r}, 3{p} +1{p} por Light carregado ao jogá-lo *e buffa toda a defesa/null chain*. Pode ser 5+. |
| `Raydn, Duskbane` (arma) | Once per Turn Action, ataque que ganha **+3{p}** se carregou (0→3); `Flurry`/`Glisten`/`Edict of Steel` dão mais swings/+1 contadores. |
| `Duty Bound Blitz (red)` | 5{p} **Go Again** (exige yellow carregado no turno). |
| `Take Flight` | 4/3/2 por 1{r}, **Go Again** se carregou. |
| `Light the Way` | 3{p} 0{r}, carga; se yellow carregado, **Go Again** no hit. |
| `Snatch`/`Bolt of Courage` | Compram no hit (Boltyn repõe acertando). |
| `Illuminate`/`Engulfing Light` | Entram na alma no hit (alimentam a AR do herói). |
| `Banneret of Salvation` | Solflare: ganha 1 vida quando carregado. |
| `Courageous Steelhand` | Attack Reaction: +1/2/3{p} se carregou. |
| `Roaring Beam`/`Edict`/`Flat Trackers` | Feather `Courage`/`Flurry`/`Agility` (mais AP e +1{p}). |

Defesa: `Toe the Line` (instant: previne 2 + Flurry), `Radiant Touch` (instant da
alma: previne 2), `Springboard Somersault`, `Gauntlets/Helm of Unity` (Unity +1{d}),
`Halo of Illumination` (Spellvoid 2), `Nullrune Boots/Robe` (Arcane Barrier — inútil
contra você, que é físico). Recursos: `Garland of Spring`, `Flat Trackers`.

### Habilidade do herói (a arma mais traiçoeira do matchup)

- "Se você carregou neste turno, seus ataques ganham **+1{p} enquanto defendidos por
  uma attack action card**."
- "Attack Reaction — Banir 1 carta da alma: ataque com {p} > base ganha **go again**"
  (sem limite por turno → a alma vira AP extra).

**Tradução:** bloquear Boltyn com carta de ataque é presenteá-lo com +1{p} — e as
cartas de ataque da Enigma são justamente `Clear Conscience`, `Enigma Chimera`,
`Spears`, `Fluid Motion`, `Manifest Muscle`, `Second Tenet`.

## Leitura do matchup

- **Boltyn é o beatdown com relógio condicional:** o deck só engrena **se conectar**
  (compra/vida/soul vêm do hit). E cada charge custou 1 carta da mão.
- **Enigma é o controle/atrito:** auras Cosmo = dano recorrente que o Boltyn **não
  tem como remover**; partida longa favorece você se não morrer nos turnos explosivos.
- O jogo se decide em duas frentes: (1) **negar os hits** com bloqueio eficiente e
  sem cartas de ataque; (2) **atrito** com o motor de auras.

## Plano por fase

- **Early:** monte o motor (`Spectral Manifestations`/`Solitary` → shield; `Astral
  Etchings` +3) e ataque com Cosmo. Não force o ataque se o Boltyn tiver carta grande
  na mão (risco de Phantasm). Segure 1-2 bloqueios **não-attack**.
- **Mid:** reveze: bloqueie o hit grande (`Valiant Thrust` 7), engula o resto; no seu
  turno, Cosmo 4–7 **todo turno**. Ele vai gastar mais cartas que você — a alma dele
  é recurso de AP, mas cada charge custa a mão dele.
- **Late:** Boltyn com alma cheia = turnos de 2-4 ataques com AR. A partir do ~6º
  turno ele seca (40 cartas, muito pitch 1/2). Não morra antes: em vez de correr para
  o dano, bloqueie o dano e aproveite o dano recorrente das auras.

## Regras decisivas e como lidar

1. **Nunca bloquear com attack action** (`Clear Conscience`/`Chimera`/`Spears`/
   `Fluid Motion`/`Manifest Muscle`/`Second Tenet`) — a habilidade dele dá +1{p}* e liga
   o jogo dele. Bloqueie com `Test of Strength` (4), `On the Horizon` (4),
   `Springboard Somersault` (2, +2 do arsenal), `Big Blue Sky` (2, +1 por blue),
   `Moon Chakra`/`Oasis Respite` e **equipamento** (`Blade Beckoner` 1+1).
2. **Phantasm (CR 8.3.13):** `Enigma Chimera` e `Spears of Surreality` são destruídos
   se ele defender com **attack action não-Illusionist 6+** — `Valiant Thrust (red)`
   carregado = **7** e `V of the Vanguard` carregado = **6+** são seus poppers. Ataque
   com Cosmo (aura — não tem Phantasm) quando ele segurar block grande; ou force ele a
   gastar o `Valiant Thrust` atacando antes.
3. **Dano físico ignorante a anti-arcano:** seus ataques de aura são físicos →
   `Halo of Illumination`/`Nullrune` do Boltyn **não param**. Ele trocar peças por
   anti-arcano é vantagem sua.
4. **`Moon Chakra`/`Oasis Respite` valem menos aqui** (não há burn/arcano significativo)
   — prefira `Test`/`On the Horizon`/`Big Blue Sky` e equipamento físico.

## Mão inicial, arsenal e equipamento

### Mão inicial (não existe mulligan no FAB)

- **1 motor** (`Spectral Manifestations`/`Solitary Companion`/habilidade do herói);
- **1 ataque/aura para pressionar** (`Clear Conscience`, `Enigma Chimera`, `Second Tenet`);
- **1 blue** para recursos;
- **1 bloqueio não-attack** (`Test of Strength`, `On the Horizon`, `Springboard`, `Big Blue Sky`).

### Arsenal

No fim do turno guarde a **melhor jogada proativa do próximo turno** (motor/ataque).
Não precisa guardar defesa — o bloqueio usa cartas da mão.

### Equipamento (1 por slot)

- **Cabeça / peito:** `Blade Beckoner Helm` + `Blade Beckoner Plating` (def 1 — físico).
- **Braços:** `Uphold Tradition` (Ward 1 → liga o Go Again das auras).
- **Pernas:** `Unflinching Foothold` (útil? Boltyn não tem Dominate — troque por
  `Silent Stilettos` só se quiser Arcane Barrier, desnecessário aqui) ou `Skycrest Keikoi`.
- **Peças Nullrune:** descartar por defesa física (`Blade Beckoner`), já que não há arcano.

## Erros que perdem o jogo

1. **Bloquear com carta de ataque** — dá +1{p}* e transforma `Valiant Thrust` em 8.
2. **Atacar com Phantasm** (`Chimera`/`Spears`) na mão cheia dele → carta destruída
   ("popada") e dano perdido.
3. **Deixar o `Valiant Thrust (red)` conectar** sem bloquear (7 de dano e ainda compra/
   soul no hit dele).
4. **Queimar blue/motor bloqueando turno pequeno** e chegar sem mão ao próprio turno.
5. **Forçar a corrida de dano** — o Boltyn tem `Toe the Line`/`Radiant Touch`/`Unity`
   para se defender; o atrito do Cosmo vence no longo prazo.

**Resumo:** controle físico — bloqueie com defesas e equipamento (nunca com ataque),
negue os hits (o relógio dele para de girar), ataque todo turno com auras do Cosmo e
não exponha seus Phantasm cards ao `Valiant Thrust`.