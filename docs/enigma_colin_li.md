# Plano de mão/jogo — Enigma (Colin Li, vp Calling Bangkok 2026)

Decklist: `data/decks/enigma_colin_li.yaml`

## Análise do deck

Pool de 55 cartas, válido no validator do repo (Silver Age / TRP 7.4).

### Estratégia central

Combo aggro de auras 2H **Cosmo**:

- `Cosmo, Scroll of Ancestral Tapestry` — auras com ward viram armas (p = ward) com
  "Once per Turn Action - {r}: Attack"; ataques de aura com +1 contadores ganham Go Again.
- `Spectral Manifestations` (2{r}, Go Again) — cria Spectral Shield e, se controlar
  **nenhuma outra** aura Illusionist, põe 3 contadores no token (shield ward 4 = ataque 4).
- `Solitary Companion` (0{r}) — mesma condição, cria shield.
- `Astral Etchings` — +3 contadores em aura ward (instant se controlar shield).

### Pitch

| Cor | Qtd | % |
|---|---|---|
| red | 22 | 50% |
| yellow | 2 | 5% |
| blue | 20 | 45% |

- Pitch médio: **1.95**.
- 21 cartas a **0{r}**: quase não precisa de pitch para sequenciar; reds servem para
  on-hit/defesa, blues pagam os intuitivos/payoff.

### Componentes

| Função | Cartas |
|---|---|
| Motor de auras/shields | Spectral Manifestations, Solitary Companion, Waxing Specter, Waning Vengeance |
| Ataques agressivos | Enigma Chimera (Phantasm 6), Clear Conscience (8 red / 6 blue), Fluid Motion (2 + Go Again), Spears of Surreality (Phantasm + GA), Second Tenet x2, Manifest Muscle |
| Defesa | Test of Strength (4{d} + Clash → Gold), On the Horizon (4{d} + scry), Big Blue Sky (+1{d} por blue pitchado), Springboard Somersault (+2{d} do arsenal) |
| Prevenção | Moon Chakra, Oasis Respite (anti arcano/burn) |
| Transcend engine | Homage to Ancestors (gain 1{h}), Pass Over (banish do cemitério), Preserve Tradition (recicla action) — todas 0{r}, blue |

## Plano de mão/jogo

Baseado em simulação de 20.000 primeiras mãos (pool de 44 cartas, mão de 4) + mecânicas do deck.

### 1. Números das primeiras mãos

| Cenário | Chance |
|---|---|
| Mão com **motor** (Spectral Manifestations / Solitary Companion / Waxing Specter / Waning Vengeance) | **56%** |
| Mão com **motor + ataque** jogável | **43%** |
| Mão com **transcend + blue** | 26% |

- **Keep** se tiver motor OU (2+ blues + ataque). Motor sem ataque ainda keep — o motor
  gera os ataques do Cosmo.
- **Mulligan** se mão só de support/custo alto sem blue (nada para gerar ataques de aura).

### 2. Ordem do Turno 1

**Regra de ouro: jogue a 1ª aura/charge INTO o shield antes de qualquer outra coisa.**

- `Spectral Manifestations` atrás de **nenhuma outra** aura Illusionist → shield ganha
  **+3 contadores** (ward 4 → ataque Cosmo 4{p} + Go Again). Jogar outra aura antes
  desperdiça o bônus.
- `Solitary Companion` (0{r}) cria shield; só tem esse efeito sem outras auras.

**Sequência padrão de 3 cards:**

```
1. Pitch blue -> recursos
2. Spectral Manifestations / Solitary Companion  (motor cria o shield)
3. Astral Etchings  (+3 contadores, instant se houver shield)
4. Cosmo -> ataca com a aura (1 AP; 1º spectral attack custa {r} menos)
5. Aproveita o Go Again -> Fluid Motion / Spears / Enigma Chimera (blue, spammable)
```

### 3. Exemplos de linhas por mão

**Mão A:** `Solitary Companion + Spectral Manifestations + Fluid Motion + Second Tenet Tide`

1. Pitch `Second Tenet Tide` → 3 resfr
2. `Spectral Manifestations` (2{r}) → shield com 3 contadores (ward 4)
3. Não jogar Solitary (o bônus do Manifestations já foi usado; guardar Solitary para
   bloqueio 2{d} ou turno 2)
4. Cosmo ataca shield 4{p} → Go Again (aura com contadores)
5. `Fluid Motion` 0{r} (2{p}, Go Again se criou card neste turno) → atropela

Linha t1: **~6-7 dano + shield ward 4 na mesa.**

**Mão B:** `Waxing Specter + Test of Strength + Clear Conscience + Oasis Respite`

1. Sem blue pitchado, Waxing Specter não ganha +1 — fraca de t1.
2. Alternativa melhor: segurar o turno — `Test of Strength` no arsenal (4{d} + Clash),
   pitch `Oasis` ou `Clear Conscience`.
3. Turno 2: limpa a mão.

Mãos **sem motor**: favorecer defender + transição, não forçar o Cosmo.

### 4. Princípios de sequenciamento

1. **Shields atacam de graça na prática** (1ª ativação custa {r} menos) — gaste AP neles
   **antes** dos ataques de mão caros; o Go Again deles financia o resto.
2. **Charge antes de atacar:** `Astral Etchings` SEMPRE antes do Cosmo na mesma aura.
3. **Guarde `Waning Vengeance`** como rede de proteção: sai da arena → cria shield se
   pitchou blue; ótima defesa contra burn/on-hit.
4. **Transcend na ordem certa:** `Homage/Pass Over/Preserve` transcende se jogou outro
   blue no turno — jogue o blue antes do transcend; `Second Tenet` por último (+2{p} pós-transcend).
5. **Pitch:** blues para os 3{amp} (Second Tenet, Clear Conscience, Manifest Muscle) —
   nunca pitchar blue se a intenção é atacar caro; reds na defensa.

### 5. Versus Briar (matchup)

- **Nullrune** contra arcano (não bloqueável) — ativar cedo, não esperar o dano.
- **Moon Chakra** (previne 3, ou 5 se transcendeu) e **Oasis Respite** (previne 4) são as
  únicas saídas a burn letal — guardar para o turno com auras carregadas.
- **Test of Strength** no arsenal + `Unflinching Foothold` → Clash + Gold no ataque dela.
- **Pass Over banishes carta do cemitério do oponente** — contra Gravy Bones, banisha um
  watery grave card quando a condição blue estiver ativa.
- Cuidado com **Embodiment of Earth**: dá +1{d} a non-attack actions defendendo — os
  ataques de Cosmo (aura shields) não são non-attack action cards e não recebem o bônus.