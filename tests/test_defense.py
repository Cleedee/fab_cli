"""Testes do sugeridor de defesa."""

from flesh_and_blood.carddb import load_cards
from flesh_and_blood.defense import ValueWeights, card_value, suggest_defense


def test_bloqueio_total_mais_barato():
    cards = load_cards()
    hand = {k: cards[k] for k in ["Snatch (red)", "Sizzle (red)", "Sigil of Suffering (red)"]}
    opts = suggest_defense(4, hand)
    best = opts[0]
    assert best.damage_taken == 0
    # Sigil (DR, def 3) + Sizzle (2) cobre 4 gastando menos valor que Snatch(4p attack)
    assert set(best.hand_cards) == {"Sigil of Suffering (red)", "Sizzle (red)"}


def test_prefere_equipamento_antes_da_mao():
    cards = load_cards()
    hand = {"Snatch (red)": cards["Snatch (red)"]}
    equip = {"Blade Beckoner Helm": 1}
    opts = suggest_defense(1, hand, equip)
    best = opts[0]
    assert best.hand_cards == ()
    assert best.equipment == ("Blade Beckoner Helm",)
    assert best.damage_taken == 0


def test_impossivel_minimiza_dano():
    cards = load_cards()
    hand = {"Snatch (red)": cards["Snatch (red)"]}  # def 2
    opts = suggest_defense(9, hand)
    best = opts[0]
    assert best.damage_taken == 7
    assert best.block_total == 2
    # opção de não bloquear existe na lista
    assert any(o.damage_taken == 9 for o in opts)


def test_dominate_limita_cartas_e_actions():
    cards = load_cards()
    keys = ["Unmovable (blue)", "Sizzle (red)", "Snatch (red)"]
    hand = {k: cards[k] for k in keys}
    opts = suggest_defense(6, hand, dominate=True)
    for o in opts:
        n = len(o.hand_cards) + len(o.equipment)
        if o.damage_taken == 0:
            assert n <= 2
            # Action card = qualquer carta com "Action" no tipo
            actions = sum(1 for k in o.hand_cards if "Action" in cards[k].types)
            assert actions <= 1
    best = opts[0]
    # Com dominate: no máx. 1 action card; Unmovable(DR)+Sizzle(action) é legal e cobre 7
    assert set(best.hand_cards) == {"Unmovable (blue)", "Sizzle (red)"}


def test_earth_bonus_da_mais_bloqueio():
    cards = load_cards()
    # Sizzle (red) é non-attack action, def 2; com Earth bonus vira 3.
    # Snatch (red) é attack action, não ganha Earth bonus.
    hand = {"Sizzle (red)": cards["Sizzle (red)"], "Snatch (red)": cards["Snatch (red)"]}
    # Incoming 4: sem Earth bonus, Sizzle(2)+Snatch(2)=4 cobre; com Earth, Sizzle sozinho(3) não
    opts_earth = suggest_defense(4, hand, earth_bonus=True)
    # Com Earth bonus, Sizzle defende com 3; ainda precisa de 1 extra (Snatch cobre)
    best_earth = opts_earth[0]
    assert best_earth.damage_taken == 0
    assert best_earth.block_total >= 4
    # Earth bonus só afeta non-attack actions: Sizzle +1, Snatch normal
    hand_only_sizzle = {"Sizzle (red)": cards["Sizzle (red)"]}
    opts_earth2 = suggest_defense(3, hand_only_sizzle, earth_bonus=True)
    assert opts_earth2[0].damage_taken == 0
    # Sem Earth, Sizzle(2) não cobre 3
    opts_normal2 = suggest_defense(3, hand_only_sizzle)
    assert opts_normal2[0].damage_taken == 1


def test_nunca_vazio():
    opts = suggest_defense(5, {}, {})
    assert len(opts) >= 1
    assert opts[0].damage_taken == 5


def test_earth_bonus_so_para_non_attack_actions():
    cards = load_cards()
    # Snatch (attack action) não ganha +1 do Earth
    hand = {"Snatch (red)": cards["Snatch (red)"]}
    opts = suggest_defense(3, hand, earth_bonus=True)
    assert opts[0].damage_taken == 1
    assert opts[0].block_total == 2


def test_pitch_influi_no_valor_da_carta():
    """Carta azul (pitch 3) tem custo de oportunidade maior que vermelha (pitch 1)."""
    cards = load_cards()
    w = ValueWeights()
    blue_card = cards["Unmovable (blue)"]  # DR, def 3, pitch 3
    red_card = cards["Sizzle (red)"]  # attack action, def 2, pitch 1
    assert card_value(blue_card, w) > card_value(red_card, w)


def test_pitch_weight_zero_ignora_pitch():
    """Com pitch_weight=0, o pitch não influencia o valor."""
    cards = load_cards()
    w = ValueWeights(pitch_weight=0)
    # Big Blue Sky (blue): DR, def 2, pitch 3, cost 0 → value = 1 + 0.25 = 1.25
    # Snatch (red): attack, def 2, pitch 1, cost 0 → value = 1 + 1.5 = 2.5
    blue_dr = cards["Big Blue Sky (blue)"]
    red_atk = cards["Snatch (red)"]
    assert card_value(blue_dr, w) == 1.25  # base + DR only
    assert card_value(red_atk, w) == 2.5  # base + attack only


def test_efficiency_propriedade():
    """Eficiência = dano prevenido / valor perdido; inf quando valor=0."""
    cards = load_cards()
    hand = {"Sizzle (red)": cards["Sizzle (red)"]}
    opts = suggest_defense(4, hand)
    for opt in opts:
        if opt.value_lost == 0:
            assert opt.efficiency == float("inf")
        else:
            prevented = max(0, opt.block_total - opt.damage_taken)
            assert opt.efficiency == prevented / opt.value_lost


def test_pitch_preenche_para_cards_equipment():
    """Equipamento (pitch None) não contribui com pitch no valor."""
    cards = load_cards()
    w = ValueWeights()
    # Blade Beckoner Helm: equipment, pitch None → pitch contribui 0
    helm = cards["Blade Beckoner Helm"]
    assert card_value(helm, w) == w.base  # sem attack, sem GA, sem DR, pitch=0


def test_cycle_score_combina_defesa_e_ofensiva():
    """cycle_score = dano prevenido + poder de ataque restante na mão."""
    cards = load_cards()
    # Snatch (red, attack, power 4) + Sizzle (red, non-attack, power None).
    # Bloquear com Sizzle → sobra Snatch (power 4) → cycle = 2(prevenido) + 4 = 6
    # Bloquear com Snatch → sobra Sizzle (power None) → cycle = 2(prevenido) + 0 = 2
    hand = {"Snatch (red)": cards["Snatch (red)"], "Sizzle (red)": cards["Sizzle (red)"]}
    opts = suggest_defense(2, hand)
    sizzle_opts = [
        o for o in opts if "Sizzle (red)" in o.hand_cards and "Snatch (red)" not in o.hand_cards
    ]
    snatch_opts = [
        o for o in opts if "Snatch (red)" in o.hand_cards and "Sizzle (red)" not in o.hand_cards
    ]
    assert sizzle_opts and snatch_opts
    assert sizzle_opts[0].cycle_score > snatch_opts[0].cycle_score
