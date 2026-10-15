# Plano de jogo — Bravo, Flattering Showman (Guardian, Silver Age)

- Deck: `data/decks/bravo_atlanta_2nd.yaml`
  (importado de `https://fabrary.net/decks/01M442CA8T3DDZ3KBKV9A2RMSV` —
  "Sunday Showdown: Atlanta 2nd"; precon base = Silver Age Chapter 1 - Bravo).
- Validado pelo `deck.validate` do repo (pool de 55, 0 erros).

## Tokens e keywords do deck (referência)

Definições conforme o Comprehensive Rules oficial
(`https://rules.fabtcg.com/en/cr/08-keywords`) e confirmadas no `data/cards.yaml`.

### Tokens (CR 8.6)

| Token | Efeito |
|---|---|
| `Might` (8.6.26) | No início do seu turno, destrua: seu próximo ataque neste turno ganha **+1{p}**. |
| `Vigor` (8.6.27) | No início do seu turno, destrua: você **ganha {r}**. |
| `Quicken` (8.6.1) | Quando você joga uma attack action ou ativa um ataque de arma, destrua: o ataque ganha **go again**. |
| `Seismic Surge` (8.6.2) | No início da sua action phase, destrua: sua próxima **Guardian attack action** deste turno custa **{r} a menos**. |

Os tokens são permanentes do tipo aura, controlados por quem foi instruído a
criá-los (CR 1.4.3). **Atenção:** as peças `Civic *` deste deck criam tokens
**sob o controle de OUTRO herói** (o oponente) — ou seja, dão poder/recurso/go
again a ele. Só disparam "quando defendem". É o custo de usar essa linha.

### Keywords de habilidade (CR 8.3)

| Keyword | Efeito |
|---|---|
| `Dominate` (8.3.4) | "Isto não pode ser defendido por mais de uma carta da mão." (equipamento ainda pode defender) |
| `Heave N` (8.3.18) | Enquanto na mão, no início da end phase você pode pagar N{r} e colocar a carta **face-up no arsenal**; se o fizer, cria N tokens `Seismic Surge`. |
| `Protect` (8.3.31) | "Você pode defender qualquer herói atacado por um oponente com isto." |
| `Battleworn` (8.3.2) | Quando a corrente de combate fecha, se isto defendeu, coloque um contador **-1{d}**. |
| `Temper` (8.3.10) | Quando a corrente fecha, se isto defendeu, coloque um contador -1{d}, depois **destrua se tiver {d} zero**. |

### Keywords de rótulo (CR 8.4)

| Keyword | Efeito |
|---|---|
| `Crush` (8.4.2) | Rótulo para habilidade triggered-static: "Crush — quando isto **causa 4 ou mais de dano**, [efeito]." Não é opcional. Dano prevenido **não** conta. |

## Como o deck vence (motor)

Guardian **midrange de "crush"**: sobrevive/defende barato, assa um ataque crush
no arsenal e o despeja com um golpe dificílimo de bloquear, ativando o efeito de
disrupção do crush.

### Habilidade do herói (a peça central)

> **Action — {r}{r}, {t}:** vire uma carta face-down no seu arsenal para face-up.
> Se ela tiver **crush**, ganha **+2{p}** e **dominate** neste turno. **Go again**.

**Tradução:** o arsenal guarda um ataque crush; no próximo turno você paga {r}{r}
e o transforma num hit com **+2{p}** de bônus e **dominate** — o oponente só
pode defender com **1 carta da mão** (equipamento à parte), então raramente
segura o dano e o **crush dispara**.

### Linha canônica (do artigo oficial)

1. Defende com 2 cartas, bate com `Titan's Fist` e no fim do turno assa um
   **crush red** (ex.: `Chokeslam (red)`, 8{p}, custo 4).
2. No turno seguinte, com **dois blues** na mão (pitch 3 + 3 = 6 recursos):
   paga {r}{r} pela habilidade (+2{p} e dominate) e 4 pelo ataque.
3. `Chokeslam (red)` ataca como **10{p} com dominate** — quase metade dos 20 de
   vida, e o crush obriga o oponente a lidar com a disrupção.

### Peças

| Categoria | Cartas | Observação |
|---|---|---|
| Arma | `Titan's Fist` (1H, martelo) | `{r}{r}{r}`: ataque 3{p}, **+1{p}** se houver carta de custo 3+ na pitch zone → 4{p}. Pressão recorrente. |
| Crush red (custo baixo, 7-8{p}) | `Boulder Drop`, `Cartilage Crush`, `Crush Confidence`, `Fault Line`, `Debilitate`, `Chokeslam` | Todo 4+ vira 9-10{p} com a habilidade. Efeitos: topo-do-deck, +{r} na 1ª ação, perde habilidades, -2{p} no 1º ataque etc. |
| Crush pesado | `Disenchantment of the Old Ones (red)` (custo 6, 10{p}, destrói auras de Guardian; Heave 2), `Macho Grande (blue)` (8{p} **Dominate** nativo), `Thunder Quake (blue)` (8{p}, Heave 3) | Fechamento / setup de Seismic Surge. |
| Crush blue (defesa) | 3{d}, custo 3-5 | Blocos sólidos que também são a linha de crush. |
| Reações | `Pummel` (+4{p} em martelo/attack action), `Staunch Response` (DR 7), `Unmovable` (DR 7 de arsenal), `Arcane Polarity` (ganha vida / 4 vs arcano) | Pummel empurra um crush acima do limiar de 4 de dano. |
| Clash / tokens | `Clash of Might/Vigor/Mountains`, `Thunk`, `Test of Might` | Defendem e, ao ganhar o clash, criam `Might`/`Vigor` para o próximo turno. |
| Equipamento | `Bastion of Duty` (off-hand, Protect+Temper), `Civic *` (Temper), `Gauntlet of Boulderhold` (Battleworn, +2{p} numa attack action), `Nullrune *` (Arcane Barrier 1) | Escolhe-se 1 por slot. |

Recursos: **21 red / 24 blue** (sem yellow). Os blues (pitch 3) são o combustível
do custo + habilidade; os reds são os golpes.

## Plano por fase

- **Início:** montar mão de defesa + 1 crush red para assar. Guardar os blues.
- **Meio:** alternar turnos de defesa eficiente (3{d}) com turnos de Titan's Fist
  + arsenal. Não queimar o crush red como pitch.
- **Fechamento:** turno de crush de 10{p} dominate + Pummel; repetir até zerar os
  20 de vida. `Thunder Quake`/`Disenchantment` geram `Seismic Surge` (Heave) para
  baratear o próximo Guardian attack.

## Erros comuns

- Usar o crush red como pitch (perde o payoff) em vez de guardá-lo no arsenal.
- Assar uma carta sem crush (a habilidade do herói não a buffa).
- Esquecer que o `Dominate` só limita **carta da mão** — o oponente ainda pode
  defender com **equipamento**.
- Equipar/deixar defender com peças `Civic` e presentear o oponente com
  `Might`/`Vigor`/`Quicken` sem necessidade.
- Contar dano no crush sem checar prevenção (bloqueio/equipamento) — o crush só
  dispara com **4+ de dano efetivamente causado** (CR 8.4.2a).
