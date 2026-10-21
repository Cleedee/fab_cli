# Plano de matchup — Enigma vs Hala (Silver Age)

- Você: **Enigma** (aura/Cosmo) — deck `data/decks/enigma_colin_li.yaml`.
- Oponente: **Hala** (Warrior / Sharpen + Zenith Blade) — deck
  `data/decks/hala_atlanta_5th.yaml` (Sunday Showdown: Atlanta 5th, Andrew
  Wilborn, 04/10/2026 — mesmo evento do `bravo_atlanta_2nd.yaml`).
  Fonte: `https://fabrary.net/decks/01M442CA8VSPTVWAJNN8MEATWA`
- Ambos validados pelo `deck.validate` do repo (pool de 55, 0 erros).
- Ver também: `docs/enigma_vs_bravo.md` (ward vs Dominate — vale integralmente
  aqui) e `docs/enigma_colin_li.md` (motor do Enigma).

## Leitura do matchup

**Corrida contra uma arma só.** Hala é aggro de **espada**: o Zenith Blade é o
único atacante, e todo o dano dele é montado **dentro do mesmo turno** (veja
Sharpen abaixo — os contadores **zeram no fim do turno**). Não existe ameaça
acumulada entre turnos; existe um **pico por turno** que você precisa absorver.

- **Vantagem do Enigma:** as auras com ward são a resposta natural a tudo —
  ward não é carta da mão, então **não paga `Ironsong Response` nem `Shove Off`**
  (os dois truques dele), e atravessa **Dominate**. E as suas peças valem mais
  que as dele: `Blade Beckoner` dá **2{d}** contra arma, enquanto **todas** as
  peças dele dão só **1{d}** (e as `Unity` dão +1 **só** quando ele também
  defende com uma carta da mão).
- **Vantagem do Hala:** bloco barato e eficiente (attack actions 3{d} + Unity),
  dois turnos explosivos com `Flurry` e a **`Humble`** que te tira as habilidades.

### O que é Sharpen (a mecânica central)

`Sharpen` (CR 8.5.58): "put a +1{p} counter on it, and then at the beginning of
the end phase, remove all +1{p} counters from it".

- Cada sharpen = **+1{p} permanente no ataque** (vale para todos os ataques da
  arma naquele turno).
- **Todos os contadores são removidos no fim do turno dele.** Você não precisa
  "desarmar" nada entre turnos — só sobreviver ao turno em que ele empilhou.

## As peças do deck

| Peça                                  | Jogo                                                                                                                                                                                |
| ------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Zenith Blade` (arma 2H)              | **3{p}** por {r}, Once per Turn. Se foi **afiada neste turno**, o **primeiro** ataque dela ganha **go again**.                                                                      |
| `Hala` (herói)                        | `{r}{r}{r}, {t}`: Sharpen → **Go again** (AP "de graça" e +1{p}).                                                                                                                   |
| `Edict of Steel (red/yel/blu)`        | 0{r}, Sharpen + **cria `Flurry token`** se limiar atingido (1+/2+/3+ contadores) + **Go again**.                                                                                    |
| `Swordmaster's Path (red/blue)`       | 1{r}, próximo ataque de espada **+3{p}** (red) e o **próximo sharpen acontece em dobro** + Go again.                                                                                |
| `Display of Craftsmanship (red/blue)` | attack reaction, 2{r}: arma **+4{p}** (red) / **+2{p}** (blue) e mais +1{p} de contador se afiada.                                                                                  |
| `Ironsong Response`                   | attack reaction 0{r}, **Reprise: +3{p} se você defendeu com uma carta da mão** neste chain link.                                                                                    |
| `Sharp Incline`                       | 0{r}, Sharpen + (≥limiar) a **próxima ativação** da arma custa **{r} a menos**.                                                                                                     |
| `Cut n' Carve (blue)`                 | 0{r}, Sharpen + (≥3 contadores) o **próximo ataque** da espada ganha **Dominate**.                                                                                                  |
| `Shove Off (blue)`                    | attack reaction 1{r}: devolve **à mão** a carta não-equipamento que defendeu um **ataque de espada** dele.                                                                          |
| `Steelblade Shunt (red)`              | defense reaction 1{r}, **6{d}** em qualquer ataque + **1 de dano** em você se for um ataque de arma.                                                                                |
| `Humble`                              | attack action 6{p} (2{r}): **on-hit — você perde todas as habilidades** até o fim do turno seguinte dele.                                                                           |
| `Toe the Line`                        | instant 0{r}: previne 2 e **cria um `Flurry token`**.                                                                                                                               |
| `Flurry token`                        | "when you activate a weapon attack, destroy this and you may **attack with the weapon twice** this turn".                                                                           |
| `Blade Dance token`                   | destroy → o ataque ganha **go again**.                                                                                                                                              |
| `Sirens of Safe Harbor`               | 2{d} e, ao ir ao cemitério, **+1{h}** para ele (bloco com Sirens = 2{d} + 1 vida).                                                                                                  |
| `On the Horizon (red)`                | **4{d}** e ele olha o topo do deck (scry 1) quando defende.                                                                                                                         |
| Armadura                              | `Helm/Gauntlets/Pillar of Unity` **1{d}** (+1{d} se defender **junto com carta da mão**, `Temper`) e `Edge Laden Plate` 1 = 4 slots de 1{d}; as peças extras **`Nullrune` = 0{d}**. |

## Os problemas que o Hala causa (e como responder)

| Ameaça                         | Efeito                                                                                            | Resposta do Enigma                                                                                                                               |
| ------------------------------ | ------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `Edict of Steel` + `Flurry`    | **Zenith ataca 2×** num mesmo turno (e com go again)                                              | **ward na mesa antes do turno dele**; cada aura destruída = 1 de prevenção sem usar a mão.                                                       |
| `Ironsong Response`            | **+3{p}** no ataque de arma **se você defendeu com carta da mão**                                 | Defenda com **equipamento + ward**. Bloco de mão só quando o dano for maior que o ganho dele (ver matemática).                                   |
| `Shove Off`                    | Devolve **sua carta de defesa à mão** e o dano atravessa                                          | Só **equipamento** resiste ao bounce; ward não é carta e não é alvo.                                                                             |
| `Cut n' Carve` (≥3 contadores) | **Dominate** no Zenith                                                                            | Ward atravessa (CR 8.3.4) **e** `Unflinching Foothold` retira o Dominate.                                                                        |
| `Humble`                       | On-hit: você **perde as habilidades** (a instant de criar Spectral Shield) no seu turno e no dele | Nunca deixe acertar. É **attack action** (não espada): **não** paga Reprise nem Shove Off — pode bloquear com a mão à vontade.                   |
| `Steelblade Shunt`             | defense reaction 1{r}: **6{d}** em qualquer ataque (+1 de dano em você se for arma)               | Só **2 cópias** e cada use custa {r} — force **dois ataques no mesmo turno** (Cosmo com go again + `Clear Conscience`) para atravessar um deles. |

**Nenhum dano dele é arcano** — mas o seu também não é: `Nullrune` dele é
**0{d}** puro. Não troque suas `Blade Beckoner` (2{d} vs arma) por Nullrune.

## Defesa — a matemática do ataque do Zenith

```
dano = 3 (base) + nº de contadores + buffs dele
         - [Blade Beckoner Helm/Plating: 2 cada vs arma]
         - [aura de ward destruída: 1 cada] - [cartas da mão] - [prevenção]
```

| Fonte de poder                                       | Quantidade          |
| ---------------------------------------------------- | ------------------- |
| Base do `Zenith Blade`                               | **3**               |
| +1 contador (1 `Edict`/herói)                        | +1                  |
| +3 contadores (Edict + herói + Display)              | +3                  |
| `Swordmaster's Path (red)`                           | **+3**              |
| `Display of Craftsmanship (red)` (reação)            | **+4**              |
| `Ironsong Response` (**só se você defendeu da mão**) | **+3**              |
| 2º swing com `Flurry token`                          | **repete o ataque** |

**Turno típico mid-game:** 3 + 2 contadores + `Swordmaster's Path` = **8{p}**;
com `Flurry` = **2 ataques ≈ 16**. Pico com tudo ligado (Display + Ironsong) =
**12-15 num único golpe**.

Fontes de defesa:

- **Equipamento:** `Blade Beckoner Helm`/`Plating` = **2{d} cada** contra arma
  (base 1 + 1 contra weapon attack) — as melhores peças do matchup;
  `Unyielding Grip` +3{d} com mão vazia; `Skycrest Keikoi` previne 1.
- **Ward:** `nº de auras destruídas × 1` (o ward base — CR 8.3.20; os contadores
  `+1{p}` aumentam só o **ataque** do Cosmo, não a prevenção). **Não é carta da
  mão** → não liga Reprise nem Shove Off.
- **Carta da mão:** `Test of Strength` (4), `On the Horizon` (4),
  `Big Blue Sky` (2 +1 por blue), attack actions (3{d}).
- **Prevenção:** `Moon Chakra` (3, ou **5** se transcendeu), `Oasis Respite` (4).
- **Anti-Dominate:** `Unflinching Foothold` — `Instant - Destroy: target attack
  loses and can't gain dominate`. Funciona no ataque de **arma** também.

**Regra de ouro:** contra `Ironsong Response`/`Shove Off`, prefira equipamento

+ ward. Se você defende com uma carta de 3{d} e ele tem o `Ironsong (+3)`, o
  bloco rende **zero** — e com o `Shove Off` rende menos que zero (a carta volta
  para a sua mão e o dano passa).

## Ataque — o que usar e o que evitar

- **Bloco do Hala (para dimensionar o seu dano):** armadura **1** sozinha (Unity
  só dá +1 **se ele também defender com uma carta da mão**); attack actions
  `Bluster Buff`/`Chest Puff`/`Brutal Assault` = **3{d}**; `Sirens` = 2{d} + 1
  vida; `On the Horizon` = 4{d}; `Steelblade Shunt` = 6{d} (custa {r}).
- **Armadura dele é baixa:** 4 slots, todos com peças de **1{d}**
  (`Helm/Gauntlets/Pillar of Unity` + `Edge Laden Plate`), e o bônus `Unity`
  (+1{d}) só entra se ele defender **junto com uma carta da mão**. Ele ainda
  pode encaixar as 3 peças **`Nullrune` (0{d})** esperando arcano — você não
  causa nenhum, então isso é **dano grátis**. O Cosmo (4-7{p}) costuma passar.
- **Phantasm (CR 8.3.13):** `Enigma Chimera` e `Spears of Surreality` são
  destruídos se ele defender com **attack action não-Illusionist de 6+{p}** —
  ele tem **9 cópias**: `Bluster Buff` (6), `Chest Puff` (7),
  `Fyendal's Fighting Spirit` (7), `Humble` (6), `Sirens of Safe Harbor (red)`
  (6). Não ataque com Phantasm com a mão dele cheia.
- **`Clear Conscience` não tem Phantasm** — é o seu ataque de hand-pressure.
- **Motor Cosmo é imune a Phantasm:** os ataques de aura não são attack action
  cards. São a sua pressão confiável.
- **Linha de dano ideal:** `Spectral Manifestations` (shield com 3 contadores) →
  Cosmo ataca com **go again** → `Fluid Motion`/`Clear Conscience`. Alvo:
  **6-8 dano/turno** — ele troca vida por mão mais rápido do que você, porque a
  armadura dele não bloqueia.

## Plano por fase

### Turnos 1-2 — montar o motor

- `Spectral Manifestations` **antes** de qualquer outra aura (garante os +3
  contadores no shield) e ataque com Cosmo todo turno.
- Ele precisa de setup (`Edict` + sharpen + `Flurry`) para valer a pena atacar:
  o turno 1 dele costuma ser fraco. **Puna com dano**.
- Deixe **1 aura com ward na mesa** antes do turno dele — é a defesa que não
  custa carta da mão.

### Turnos 3-5 — absorver o pico

- Sinais de turno grande dele: 3+ cartas na mão + azul pitchado (o hero ability
  custa **3 recursos**). Se ele assou carta no turno anterior, **espere 2
  ataques de Zenith**.
- Defenda com **equipamento + ward**; guarde as cartas da mão para o dano que
  não dá para prevenir e para **não alimentar** o `Ironsong Response`.
- `Unflinching Foothold` fica **guardada** para o Zenith com Dominate
  (`Cut n' Carve`); `Humble` bloqueie com a mão **sempre** (não é ataque de
  arma).

### Fechamento — matar no atrito

- Contadores dele **zeram todo turno**; o **seu** ward e a aura ficam. Partida
  longa favorece você **se não morrer no pico**.
- Reúna 2 shields / ataques de aura + `Second Tenet` (+2{p} pós-transcend) e
  feche — ele não tem remoção de aura, só bloco.

## Equipamento recomendado contra Hala

| Slot   | Cartas                                 | Nota                                                                          |
| ------ | -------------------------------------- | ----------------------------------------------------------------------------- |
| Arma   | `Cosmo` (2H)                           | Obrigatório.                                                                  |
| Cabeça | `Blade Beckoner Helm`                  | **2{d} vs Zenith** (base 1 +1 contra arma). **`Nullrune Hood` = 0{d}**, fora. |
| Peito  | `Blade Beckoner Plating`               | **2{d} vs Zenith**; `Nullrune Robe` = 0{d}, fora.                             |
| Braços | `Uphold Tradition` / `Unyielding Grip` | Ward 1 (liga o go again) / +3{d} com mão vazia.                               |
| Pernas | **`Unflinching Foothold`**             | Retira o **Dominate** do Zenith; 1{d}.                                        |
| Extra  | `Skycrest Keikoi`                      | Previne 1.                                                                    |

## Checklist rápido

- [ ] Suas peças `Nullrune` **fora** (Hala é 100% físico) — e se ele encaixar as
  
      dele, é **dano grátis** (0{d}).
- [ ] `Blade Beckoner Helm` + `Plating` equipados: **2{d} cada** vs Zenith.
- [ ] **1 aura com ward na mesa** antes de cada turno dele.
- [ ] Não defender com carta da mão se ele tem 2+ na mão (`Ironsong +3` /
  
      `Shove Off`); use equipamento + ward.
- [ ] `Unflinching Foothold` reservada para o Zenith com **Dominate**.
- [ ] `Humble` **nunca** acerta (perde a instant de shield por um turno).
- [ ] Sem Phantasm (`Chimera`/`Spears`) com **6+{p}** de ataque action na mão dele.
- [ ] Contadores dele **zeram no fim do turno** — não entre em pânico com a
  
      espada "crescida"; entre em pânico com `Flurry` (2 swings).
