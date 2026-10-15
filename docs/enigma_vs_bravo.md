# Plano de matchup — Enigma vs Bravo, Flattering Showman

- Você: **Enigma** (aura/Cosmo) — deck `data/decks/enigma_colin_li.yaml`.
- Oponente: **Bravo, Flattering Showman** (Guardian crush) — deck
  `data/decks/bravo_atlanta_2nd.yaml`.
- Ver também: `docs/bravo_flattering_showman.md` (tokens/keywords e motor do Bravo).

## Leitura do matchup

**Corrida com pivô defensivo.** Enigma é o agressor e é mais rápido; Bravo é
midrange que aguenta, assa um crush no arsenal e despeja um golpe de **9-10{p}
com Dominate** que dispara um efeito de crush (disrupção). Enigma precisa
**matar antes de levar 2 desses**, ou sobreviver ao turno-chave com prevenção.

- **Vantagem do Enigma:** velocidade e **ward**. As auras com ward (Spectral
  Shield etc.) são a resposta natural ao **Dominate** — veja abaixo.
- **Vantagem do Bravo:** blocos eficientes (attack actions 3{d}) e os efeitos de
  crush que desmontam o turno do Enigma.

### Por que ward responde ao Dominate

`Dominate` (CR 8.3.4) = "não pode ser defendido por mais de **uma carta da
mão**". Ward **não defende com carta da mão**: destruir a aura previne dano = ward
+ contadores. Então a aura carregada atravessa o Dominate. É o principal
"escudo" do Enigma contra o turno de crush.

## Os 4 problemas que o Bravo causa (e como responder)

| Ameaça (crush do Bravo) | Efeito | Resposta do Enigma |
|---|---|---|
| `Debilitate` | Seu 1º ataque do turno leva **-2{p}** | Ataque com **Cosmo/aura** primeiro (ou aceite; -2 só no 1º). |
| `Cartilage Crush` | Sua 1ª ação do turno custa **+{r}** | Separe um blue de pitch; ou jogue a ação barata (0{r}) primeiro. |
| `Crush Confidence` | Você **perde as habilidades** | **Grave para o Enigma:** perde a instant de criar Spectral Shield. Tente prevenir esse crush (mantenha ward/disposição). |
| `Chokeslam` | Suas **attack actions não ganham {p}** | Não conte com buffs (Manifest Muscle, Pummel) nesse turno; use auras. |
| `Crush the Weak` | Não pode jogar attack actions de **≤3{p}** | Trava `Fluid Motion`/`Spears`; senão o turno vira só Cosmo/defesa. |
| `Disable` | Um **arsenal** seu vai ao fundo do deck | Não dependa de `Springboard Somersault`/`Test of Strength` no arsenal. |

Nenhum desses danos é arcano — **Nullrune é peso morto neste matchup**.

## Defesa — a matemática do turno de crush (10{p} Dominate)

Você só pode usar **1 carta da mão**. Some tudo o mais:

```
10 (ataque) - [1 carta da mão] - [equipamento] - [prevenção/ward] <= 3  -> crush não dispara
```

Fontes:
- **Carta da mão:** `Test of Strength` (4{d}), `On the Horizon` (4{d}),
  `Big Blue Sky` (2{d}+1 por blue pitchado), attack actions (3{d}).
- **Equipamento:** `Blade Beckoner Plating`/`Helm` (1{d} cada),
  `Unyielding Grip` (+3{d} se mão vazia).
- **Ward:** destruir a aura previne ward+contadores. Spectral Shield do motor
  chega a **ward 4-7** (Manifestations +3, Etchings +3).
- **Prevenção:** `Moon Chakra` (3, ou **5** se transcendeu), `Oasis Respite` (4).

**Truque central — `Unflinching Foothold`:** `Instant - Destroy: target attack
loses and can't gain dominate`. Destrua no turno do crush: o ataque perde
Dominate e **você volta a defender com várias cartas da mão** (ex.: 4+4+3 = 11,
previne os 10). É a carta de ouro da matchup — **guarde-a sempre** para o turno
de crush, não gaste como bloco comum.

## Ataque — o que usar e o que evitar

- **Prefira não-Phantasm:** `Clear Conscience` (red 8{p} / blue 6{p}) é o
  cavalo de batalha. `Enigma Chimera` (6{p}) e `Spears of Surreality` são
  **Phantasm** — o Bravo defende com **attack action de 6+{p}** e a sua é
  **destruída** (ele tem muitas: Chokeslam 6/8, Debilitate 6/8, Disable 7,
  Boulder Drop 7...). Só use-os quando ele estiver sem essas cartas na mão.
- **Motor Cosmo é imune a Phantasm:** ataques de aura (Spectral Shield etc.)
  não são attack action cards. São a sua pressão confiável — e com +1 contador
  ganham **go again**.
- **Linha de dano ideal t1-t2:** `Spectral Manifestations` (shield ward 4) →
  Cosmo ataca 4{p} + go again → `Fluid Motion`/`Second Tenet`/`Clear Conscience`.
  Alvo: **6-8 dano/turno**.

## Plano por fase

### Turnos 1-2 — correr
- Monte o Cosmo o mais rápido possível: `Spectral Manifestations` **antes** de
  qualquer outra aura (garante os +3 contadores no shield).
- Ataque com o shield (go again) e emende `Fluid Motion`/`Clear Conscience`.
- Não pique o crush dele mentalmente — você **não** interage com o arsenal dele;
  priorize dano.
- Já deixe **um ward na mesa** para o turno dele (o shield que não atacou serve).

### Turnos 3-4 — o turno-chave dele
- Bravo precisa de **2 blues (6 recursos) + 1 crush no arsenal**. Se você viu
  ele assar carta no turno anterior e ficar com a mão cheia de blue, **espere o
  crush**.
- Guarde para esse turno: **`Unflinching Foothold`** (remove Dominate) **e**
  `Moon Chakra`/`Oasis Respite`/`Test of Strength` (bloco grande).
- Depois de sobreviver, ele gastou a mão e os recursos → **contra-ataca forte**.

### Turno de fechamento — matar antes do 2º crush
- Reúna 2 shields / ataques de aura + `Second Tenet` (+2{p} pós-transcend).
- `Clear Conscience` on-hit põe carta da mão de cada herói no fundo e cria
  `Ponder` (compra no fim do turno) — bom para recompor a mão pós-turno-chave.

## Equipamento recomendado contra Bravo

| Slot | Cartas | Nota |
|---|---|---|
| Arma | `Cosmo` (2H) | Obrigatório. |
| Cabeça | `Blade Beckoner Helm` | 1{d} vs weapon; **evite `Nullrune Hood`** (arcano inútil). |
| Peito | `Blade Beckoner Plating` | 1{d} vs weapon. |
| Braços | `Unyielding Grip` | +3{d} com mão vazia (pós-ataque). |
| Pernas | **`Unflinching Foothold`** | **Anti-Dominate** — a peça-chave da matchup. |
| Extra | `Skycrest Keikoi`, `Uphold Tradition` | Prevenção 1 / +1 contador em ward. |

## Checklist rápido

- [ ] Nullrune **fora** (Bravo não tem arcano).
- [ ] `Unflinching Foothold` **reservado** para o turno de crush.
- [ ] 1 ward na mesa **todo** turno dele.
- [ ] Não atacar com Phantasm (`Chimera`/`Spears`) se ele tem 6+{p} na mão.
- [ ] Prevenção contada: `10 - bloco - equip - ward/prevenção ≤ 3` mata o crush.
- [ ] Correr: alvo ~6-8 dano/turno, matar antes do **2º** crush.
