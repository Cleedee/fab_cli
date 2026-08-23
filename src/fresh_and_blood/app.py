"""Assistente de decisão FaB — TUI Textual (Fase 3).

Interface interativa no terminal para partidas Silver Age.
O usuário controla AMBOS os lados via comandos textuais.
"""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Footer, Header, Input, RichLog, Static

from fresh_and_blood import attack as atk
from fresh_and_blood import combat as cmb
from fresh_and_blood import defense as dfs
from fresh_and_blood import probabilities as prob
from fresh_and_blood import recorder as rec
from fresh_and_blood.carddb import load_cards
from fresh_and_blood.models import (
    Card,
    GameState,
    Hero,
    new_game,
)

# ── Heróis do matchup inicial ──────────────────────────────────────────

BRIAR = Hero(
    key="Briar, Warden of Thorns",
    name="Briar, Warden of Thorns",
    life=20,
    intellect=4,
    classes=("Runeblade",),
    talents=("Earth", "Lightning"),
)
ENIGMA = Hero(
    key="Enigma",
    name="Enigma",
    life=20,
    intellect=4,
    classes=("Illusionist",),
    talents=("Mystic",),
)

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DECK_DIR = DATA_DIR / "decks"
LOG_DIR = DATA_DIR / "logs"

# ── Constantes de carta (chaves) ───────────────────────────────────────

WEAPONS = {"Briar, Warden of Thorns": "Star Fall", "Enigma": "Cosmo, Scroll of Ancestral Tapestry"}

HERO_LABELS = {"A": "Briar (A)", "B": "Enigma (B)"}


# ── Helpers ────────────────────────────────────────────────────────────


def _card_display(key: str, card: Card) -> str:
    """Formata uma carta para exibição: Nome (cor) [Poder/Defesa]."""
    parts = [key]
    if card.power is not None:
        parts.append(f"[bold]{card.power}{{p}}[/]")
    if card.defense is not None:
        parts.append(f"[bold]{card.defense}{{d}}[/]")
    if card.cost:
        parts.append(f"{card.cost}{{r}}")
    if card.pitch:
        parts.append(f"pitch {card.pitch}")
    return " — ".join(parts)


def _short_key(key: str) -> str:
    """Versão curta de uma chave de carta para comandos."""
    return key


def _find_card(partial: str, cards: dict[str, Card]) -> str | None:
    """Busca carta por nome parcial (case-insensitive)."""
    partial = partial.lower()
    for key in cards:
        if partial in key.lower():
            return key
    return None


# ── Widgets ────────────────────────────────────────────────────────────


class PlayerPanel(Vertical):
    """Painel de um jogador: vida, mão, arsenal, recursos, auras."""

    DEFAULT_CSS = """
    PlayerPanel {
        border: solid $secondary;
        padding: 0 1;
        height: 100%;
    }
    PlayerPanel > Static {
        margin: 0;
    }
    """

    def __init__(self, side: str, hero: Hero, label: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.side = side
        self.hero = hero
        self.label_text = label
        self.border_title = label

    def compose(self) -> ComposeResult:
        yield Static(id=f"life-{self.side}")
        yield Static(id=f"res-{self.side}")
        yield Static(id=f"hand-{self.side}")
        yield Static(id=f"arsenal-{self.side}")
        yield Static(id=f"auras-{self.side}")
        yield Static(id=f"equip-{self.side}")

    def refresh_from(self, state: GameState, cards: dict[str, Card]) -> None:
        p = state.players[self.side]

        # Vida com barra visual
        bar_len = 20
        filled = max(0, p.life)
        empty = bar_len - filled
        life_bar = "█" * filled + "░" * empty
        self.query_one(f"#life-{self.side}", Static).update(f"[bold]Vida:[/] {p.life} {life_bar}")

        # Recursos, AP, pitch
        ap_symbol = "●" if p.action_points > 0 else "○"
        pitch_available = sum((cards[key].pitch or 0) if key in cards else 0 for key in p.hand)
        self.query_one(f"#res-{self.side}", Static).update(
            f"[bold]AP:[/] {ap_symbol} {p.action_points}  "
            f"[bold]Pool:[/] {p.pitch_pool}{{r}}  "
            f"[bold]Pitch disp:[/] {pitch_available}"
        )

        # Mão
        hand_lines = []
        if p.hand:
            for i, key in enumerate(p.hand, 1):
                card = cards.get(key)
                if card:
                    hand_lines.append(f" [bold]{i:2}.[/] {_card_display(key, card)}")
                else:
                    hand_lines.append(f" [bold]{i:2}.[/] {key} [?]")
        else:
            hand_lines.append(" (vazia)")
        self.query_one(f"#hand-{self.side}", Static).update(
            "[bold]Mão:[/]\n" + "\n".join(hand_lines)
        )

        # Arsenal
        if p.arsenal:
            c = cards.get(p.arsenal)
            txt = _card_display(p.arsenal, c) if c else p.arsenal
        else:
            txt = "(vazio)"
        self.query_one(f"#arsenal-{self.side}", Static).update(f"[bold]Arsenal:[/] {txt}")

        # Auras
        aura_lines = []
        for key, copies in p.auras.items():
            for i, cnt in enumerate(copies):
                aura_lines.append(f"  {key} (+{cnt})")
        if not aura_lines:
            aura_lines.append(" (nenhuma)")
        self.query_one(f"#auras-{self.side}", Static).update(
            "[bold]Auras:[/]\n" + "\n".join(aura_lines)
        )

        # Equipamentos
        eq_lines = []
        for key, uses in p.equipment_uses.items():
            status = f"{uses} usos" if uses is not None else "∞"
            destroyed = " [red][Destruído][/]" if key in p.equipment_destroyed else ""
            used = " [yellow](usado)[/]" if key in p.equipment_used_this_turn else ""
            eq_lines.append(f"  {key}: {status}{used}{destroyed}")
        for key in p.equipment_destroyed:
            if key not in p.equipment_uses:
                eq_lines.append(f"  {key}: [red]Destruído[/]")
        if not eq_lines:
            eq_lines.append(" (nenhum)")
        self.query_one(f"#equip-{self.side}", Static).update(
            "[bold]Equipamentos:[/]\n" + "\n".join(eq_lines)
        )


# ── Aplicação principal ────────────────────────────────────────────────


class FaBApp(App[None]):
    """TUI do assistente de decisão FaB Silver Age."""

    TITLE = "Flesh and Blood — Silver Age"
    CSS = """
    Screen {
        background: $surface;
    }

    #body {
        height: 1fr;
        min-height: 18;
    }

    PlayerPanel {
        height: 100%;
    }

    #panel-a, #panel-b {
        width: 33%;
        min-width: 30;
    }

    #panel-center {
        width: 34%;
        min-width: 24;
        border: solid $secondary;
        padding: 0 1;
    }

    #notices-box {
        height: 6;
        min-height: 4;
        border: solid $primary;
        margin-top: 0;
    }

    #notices-log {
        height: 100%;
    }

    #command-input {
        dock: bottom;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("ctrl+q", "quit", "Sair", priority=True),
        Binding("f1", "show_help", "Ajuda"),
        Binding("tab", "switch_side", "Trocar lado"),
        Binding("f5", "suggest_defense", "Sugerir defesa"),
        Binding("f6", "plan_attack", "Planejar ataque"),
    ]

    # Estado reativo — incrementado após cada mutação
    version: reactive[int] = reactive(0)
    game_state: GameState
    cards: dict[str, Card]
    notices: list[str]
    session_log: rec.SessionLog

    def __init__(self, state: GameState, cards_dict: dict[str, Card]) -> None:
        super().__init__()
        self.game_state = state
        self.cards = cards_dict
        self.notices = []
        self.session_log = rec.SessionLog(
            hero_a=BRIAR.name,
            hero_b=ENIGMA.name,
            start_time=__import__("datetime").datetime.now().isoformat(timespec="seconds"),
        )

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="body"):
            yield PlayerPanel("A", BRIAR, "Briar (A) — Atacante", id="panel-a")
            yield self._center_panel()
            yield PlayerPanel("B", ENIGMA, "Enigma (B) — Defensor", id="panel-b")
        yield self._notices_area()
        yield Input(id="command-input", placeholder="Digite um comando (help para ajuda)...")
        yield Footer()

    def _center_panel(self) -> Static:
        """Painel central: chain link + sugestões."""
        return Static(id="panel-center")

    def _notices_area(self) -> Vertical:
        return Vertical(
            RichLog(id="notices-log", highlight=True, markup=True, max_lines=50),
            id="notices-box",
        )

    # ── Ciclo de vida ──────────────────────────────────────────────

    def on_mount(self) -> None:
        """Inicializa a tela e mostra boas-vindas."""
        self._log_notice("[bold green]⚔ FaB Silver Age — Assistente de Decisão[/]")
        self._log_notice("Briar (A) vs Enigma (B) — Turno 1. Comandos: [bold]help[/] para lista.")
        self._log_notice('[dim]Mão inicial: adicione cartas com [bold]draw "Nome (cor)"[/].[/]')
        self._refresh_all()

    # ── Notificações ──────────────────────────────────────────────

    def _log_notice(self, msg: str) -> None:
        self.notices.append(msg)
        log = self.query_one("#notices-log", RichLog)
        log.write(msg)

    def _record(self, action: str, description: str, **kwargs) -> None:
        """Registra uma ação no log da sessão."""
        self.session_log.record(
            self.game_state,
            action=action,
            description=description,
            **kwargs,
        )

    def _notify(self, msg: str) -> None:
        """Notificação breve (usada para erros)."""
        self._log_notice(f"[red]{msg}[/]")

    # ── Refresh ───────────────────────────────────────────────────

    def _refresh_all(self) -> None:
        """Atualiza todos os painéis com o estado atual."""
        self.version += 1
        panel_a = self.query_one("#panel-a", PlayerPanel)
        panel_b = self.query_one("#panel-b", PlayerPanel)
        panel_a.refresh_from(self.game_state, self.cards)
        panel_b.refresh_from(self.game_state, self.cards)
        self._update_center()
        self._update_command_placeholder()

    def _update_center(self) -> None:
        """Atualiza o painel central com chain link e sugestões."""
        lines = []
        active = self.game_state.active_player

        # Chain link ativo
        link = cmb.current_link(self.game_state, active)
        if link:
            card = self.cards.get(link.card_key)
            name = card.name if card else link.card_key
            lines.append(f"[bold cyan]▶ Chain Link:[/] {name}")
            lines.append(
                f"   Dano total: {link.total_damage}{{p}}  "
                f"Bloqueado: {link.blocked_damage}  "
                f"Restante: {link.damage_remaining}"
            )
            if link.arcane_damage:
                lines.append(f"   Dano arcano: {link.arcane_damage}")
            if link.dominate:
                lines.append("   [yellow]Dominate ativo[/]")
            lines.append(f"   Bloqueio: {link.blocked_by or 'nenhum'}")
        else:
            lines.append("[dim]Nenhum chain link ativo.[/]")

        # Vida do oponente / lethal
        opp = self.game_state.players["B" if active == "A" else "A"]
        lines.append("")
        lines.append(f"[bold]Oponente:[/] {opp.life}/20 de vida")

        # Log count
        lines.append("")
        lines.append(f"[dim]📝 {len(self.session_log.entries)} ações registradas[/]")

        # Ajuda rápida
        lines.append("")
        lines.append("[dim]Comandos: F1=ajuda, F5=defesa, F6=ataque, Tab=troca[/]")

        self.query_one("#panel-center", Static).update("\n".join(lines))

    def _update_command_placeholder(self) -> None:
        """Atualiza placeholder do input com dica contextual."""
        inp = self.query_one("#command-input", Input)
        active = self.game_state.active_player
        lbl = HERO_LABELS.get(active, active)
        inp.placeholder = f"[{lbl}] Digite um comando (help para lista)..."

    # ── Processamento de comandos ─────────────────────────────────

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Processa um comando digitado."""
        raw = event.value.strip()
        if not raw:
            return
        inp = self.query_one("#command-input", Input)
        inp.clear()
        try:
            self._exec(raw)
        except (cmb.CombatError, ValueError) as e:
            self._notify(f"Erro: {e}")
        except BaseException as e:
            if isinstance(e, (KeyboardInterrupt, SystemExit)):
                raise
            self._notify(f"Erro inesperado: {type(e).__name__}: {e}")
        self._refresh_all()

    def _exec(self, raw: str) -> None:
        """Executa um comando (dispatcher)."""
        parts = shlex.split(raw)
        if not parts:
            return
        cmd = parts[0].lower()
        args = parts[1:]

        dispatch = {
            "help": self._cmd_help,
            "draw": self._cmd_draw,
            "pitch": self._cmd_pitch,
            "arsenal": self._cmd_arsenal,
            "play": self._cmd_play,
            "attack": self._cmd_attack,
            "weapon": self._cmd_weapon,
            "boost": self._cmd_boost,
            "arcane": self._cmd_arcane,
            "defend": self._cmd_defend,
            "equip": self._cmd_equip,
            "resolve": self._cmd_resolve,
            "next": self._cmd_next,
            "switch": self._cmd_switch,
            "plan": self._cmd_plan,
            "suggest": self._cmd_suggest,
            "prob": self._cmd_prob,
            "status": self._cmd_status,
            "clear": self._cmd_clear,
            "": lambda a: None,
        }
        handler = dispatch.get(cmd)
        if handler is None:
            self._notify(f"Comando desconhecido: '{cmd}'. Digite 'help'.")
            return
        handler(args)

    # ── Comandos ─────────────────────────────────────────────────

    def _cmd_help(self, args: list[str]) -> None:
        """Mostra lista de comandos."""
        self._log_notice("[bold underline]Comandos disponíveis:[/]")
        self._log_notice("  [bold]draw[/] <carta>           — adiciona carta à mão do ativo")
        self._log_notice("  [bold]pitch[/] <carta>          — dá pitch de uma carta da mão")
        self._log_notice("  [bold]arsenal[/] <carta>        — coloca carta no arsenal")
        self._log_notice("  [bold]play[/] <carta>           — joga non-attack action")
        self._log_notice("  [bold]attack[/] <carta>         — declara ataque [dominate=...]")
        self._log_notice("  [bold]weapon[/]                  — ataca com a arma")
        self._log_notice("  [bold]boost[/] <N>               — +N{p} no link atual")
        self._log_notice("  [bold]arcane[/] <N>              — +N arcano no link atual")
        self._log_notice("  [bold]defend[/] <carta> [carta] — bloqueia link oponente")
        self._log_notice("  [bold]equip[/] <equip>           — usa equipamento p/ defesa")
        self._log_notice("  [bold]resolve[/] [ward=N] [arcane=N] — resolve link")
        self._log_notice("  [bold]next[/]                    — encerra turno / avança")
        self._log_notice("  [bold]switch[/]                  — troca jogador ativo")
        self._log_notice("  [bold]plan[/]                    — sugere linha de ataque")
        self._log_notice("  [bold]suggest[/]                 — sugere bloqueio")
        self._log_notice("  [bold]prob[/] <copias> <deck> <compras> [min] — probabilidade")
        self._log_notice("  [bold]status[/]                  — estado completo")
        self._log_notice("  [bold]clear[/]                   — limpa notificações")
        self._log_notice("  [bold]help[/]                    — esta mensagem")

    def _cmd_draw(self, args: list[str]) -> None:
        """draw <carta> — adiciona à mão do jogador ativo."""
        if not args:
            raise ValueError("uso: draw <carta>")
        key = self._resolve_card(" ".join(args))
        p = self.game_state.players[self.game_state.active_player]
        p.hand.append(key)
        self._log_notice(f"{self.game_state.active_player} comprou: {key}")

    def _cmd_pitch(self, args: list[str]) -> None:
        """pitch <carta> — dá pitch da mão."""
        if not args:
            raise ValueError("uso: pitch <carta>")
        key = self._resolve_card(" ".join(args))
        val = cmb.pitch(self.game_state, self.game_state.active_player, key, self.cards)
        self._log_notice(f"{key} pichada: +{val}{{r}}")

    def _cmd_arsenal(self, args: list[str]) -> None:
        """arsenal <carta> — coloca no arsenal."""
        if not args:
            raise ValueError("uso: arsenal <carta>")
        key = self._resolve_card(" ".join(args))
        cmb.place_arsenal(self.game_state, self.game_state.active_player, key)
        self._log_notice(f"{key} colocada no arsenal.")

    def _cmd_play(self, args: list[str]) -> None:
        """play <carta> — joga non-attack action."""
        if not args:
            raise ValueError("uso: play <carta>")
        key = self._resolve_card(" ".join(args))
        notices = cmb.play_action(self.game_state, self.game_state.active_player, key, self.cards)
        for n in notices:
            self._log_notice(f"⚡ {n.text}")

    def _cmd_attack(self, args: list[str]) -> None:
        """attack <carta> [dominate=1] — declara ataque."""
        if not args:
            raise ValueError("uso: attack <carta> [dominate=1]")
        dominate = False
        card_args = [a for a in args if "dominate" not in a.lower()]
        for a in args:
            if "dominate" in a.lower():
                dominate = True
        key = self._resolve_card(" ".join(card_args))
        link = cmb.declare_attack(
            self.game_state,
            self.game_state.active_player,
            key,
            self.cards,
            dominate=dominate,
        )
        self._log_notice(
            f"⚔ Ataque declarado: {key} ({link.total_damage}{{p}})"
            f"{' [yellow]Dominate[/]' if dominate else ''}"
        )

    def _cmd_weapon(self, args: list[str]) -> None:
        """weapon — ataca com a arma."""
        hero_key = self.game_state.players[self.game_state.active_player].hero_key
        weapon_key = WEAPONS.get(hero_key)
        if not weapon_key:
            raise cmb.CombatError(f"Arma não definida para {hero_key}")
        card = self.cards.get(weapon_key)
        if not card:
            raise cmb.CombatError(f"Arma {weapon_key} não encontrada no registro")
        link = cmb.declare_attack(
            self.game_state,
            self.game_state.active_player,
            weapon_key,
            self.cards,
            is_weapon=True,
            resource_cost=1,
            go_again_earned=False,
        )
        self._log_notice(f"⚔ Ataque de arma: {weapon_key} ({link.total_damage}{{p}})")

    def _cmd_boost(self, args: list[str]) -> None:
        """boost <N> — +N power no link atual."""
        if not args:
            raise ValueError("uso: boost <N>")
        amount = int(args[0])
        n = cmb.boost_link(self.game_state, self.game_state.active_player, amount)
        self._log_notice(n.text)
        self._record("boost", f"+{amount}{{p}}")

    def _cmd_arcane(self, args: list[str]) -> None:
        """arcane <N> — +N arcano no link atual."""
        if not args:
            raise ValueError("uso: arcane <N>")
        amount = int(args[0])
        n = cmb.set_arcane_on_link(self.game_state, self.game_state.active_player, amount, None)
        self._log_notice(n.text)
        self._record("arcane", f"+{amount}{{a}}")

    def _cmd_defend(self, args: list[str]) -> None:
        """defend <carta> [carta ...] — bloqueia com cartas da mão."""
        if not args:
            raise ValueError("uso: defend <carta> [carta ...]")
        defender = self.game_state.opponent_of(self.game_state.active_player)
        keys = []
        for a in args:
            key = self._resolve_card(a)
            keys.append(key)
        notices = cmb.defend_link(self.game_state, defender, keys, self.cards)
        for n in notices:
            self._log_notice(f"🛡 {n.text}")

    def _cmd_equip(self, args: list[str]) -> None:
        """equip <nome> — usa equipamento para defesa."""
        if not args:
            raise ValueError("uso: equip <nome>")
        defender = self.game_state.opponent_of(self.game_state.active_player)
        key = self._resolve_card(" ".join(args))
        gained = cmb.use_equipment_defense(self.game_state, defender, key, self.cards)
        self._log_notice(f"🛡 Equipamento {key}: +{gained} de bloqueio.")

    def _cmd_resolve(self, args: list[str]) -> None:
        """resolve [ward=N] [arcane=N] — resolve o link atual."""
        ward = 0
        arcane_prevented = 0
        for a in args:
            if a.lower().startswith("ward="):
                ward = int(a.split("=", 1)[1])
            elif a.lower().startswith("arcane="):
                arcane_prevented = int(a.split("=", 1)[1])
        result = cmb.resolve_link(
            self.game_state,
            self.cards,
            ward_prevented=ward,
            arcane_prevented=arcane_prevented,
        )
        self._log_notice(
            f"💥 Resolvido: {result['physical']}{{p}} físico + {result['arcane']}{{a}} arcano"
            f" → {'[red]ACERTOU[/]' if result['hit'] else '[blue]BLOQUEADO[/]'}"
        )
        for n in result["notices"]:
            self._log_notice(f"⚡ {n.text}")

    def _cmd_next(self, args: list[str]) -> None:
        """next — encerra o turno do ativo e inicia o do oponente."""
        cmb.end_turn(self.game_state)
        new_active = self.game_state.active_player
        notices = cmb.start_turn(self.game_state, new_active)
        self._log_notice(
            f"⏭ Turno {self.game_state.turn} — agora joga {HERO_LABELS.get(new_active, new_active)}"
        )
        for n in notices:
            self._log_notice(f"⚡ {n.text}")

    def _cmd_switch(self, args: list[str]) -> None:
        """switch — troca o lado 'ativo' (quem ataca/age)."""
        cur = self.game_state.active_player
        new = "B" if cur == "A" else "A"
        self.game_state.active_player = new
        self._log_notice(f"🔄 Lado ativo: {HERO_LABELS.get(new, new)}")

    def _cmd_plan(self, args: list[str]) -> None:
        """plan — mostra sugestão de linha de ataque."""
        hero_key = self.game_state.players[self.game_state.active_player].hero_key
        weapon_key = WEAPONS.get(hero_key)
        opp = self.game_state.opponent_of(self.game_state.active_player)
        opp_life = self.game_state.players[opp].life

        plan = atk.plan_attack(
            self.game_state,
            self.game_state.active_player,
            self.cards,
            opponent_life=opp_life,
            weapon_key=weapon_key,
        )
        self._log_notice("[bold cyan]📋 Plano de ataque sugerido:[/]")
        if plan.sequence:
            self._log_notice(f"  Sequência: {' → '.join(plan.sequence)}")
        else:
            self._log_notice("  [dim]Nenhuma carta para jogar.[/]")
        self._log_notice(
            f"  Dano físico: {plan.physical}  Arcano: {plan.arcane}  Total: {plan.total}"
        )
        self._log_notice(f"  Letal: {'[red]SIM[/]' if plan.lethal else '[green]não[/]'}")
        if plan.pitched:
            self._log_notice(f"  Pitch: {', '.join(plan.pitched)}")
        for n in plan.notes:
            self._log_notice(f"  [dim]• {n}[/]")

    def _cmd_suggest(self, args: list[str]) -> None:
        """suggest — sugere bloqueio para o defensor."""
        defender = self.game_state.opponent_of(self.game_state.active_player)
        attacker = self.game_state.active_player
        link = cmb.current_link(self.game_state, attacker)
        if link is None:
            self._log_notice("[yellow]Nenhum ataque ativo para defender.[/]")
            return
        p = self.game_state.players[defender]
        hand = {k: self.cards[k] for k in p.hand if k in self.cards}
        equip = {
            k: (self.cards[k].defense or 0)
            for k in p.equipment_uses
            if k not in p.equipment_destroyed
            and k not in p.equipment_used_this_turn
            and k in self.cards
            and self.cards[k].defense
        }

        earth_bonus = bool(p.auras.get(cmb.EMBODIMENT_EARTH))
        opts = dfs.suggest_defense(
            link.damage_remaining,
            hand,
            equip or None,
            dominate=link.dominate,
            top=3,
            earth_bonus=earth_bonus,
        )
        self._log_notice("[bold yellow]🛡 Sugestões de defesa:[/]")
        for i, opt in enumerate(opts, 1):
            hand_str = ", ".join(opt.hand_cards) if opt.hand_cards else "(nenhuma)"
            equip_str = ", ".join(opt.equipment) if opt.equipment else "(nenhum)"
            self._log_notice(
                f"  {i}. "
                f"Mão: {hand_str}  "
                f"Equip: {equip_str}  "
                f"Bloqueio: {opt.block_total}  "
                f"Dano: {opt.damage_taken}  "
                f"Valor: {opt.value_lost:.1f}"
            )

    def _cmd_prob(self, args: list[str]) -> None:
        """prob <copias> <deck> <compras> [min=1] — probabilidade hipergeométrica."""
        if len(args) < 3:
            raise ValueError("uso: prob <copias> <deck> <compras> [min=1]")
        copies = int(args[0])
        deck = int(args[1])
        draws = int(args[2])
        min_count = int(args[3]) if len(args) > 3 else 1
        if min_count == 1:
            p = prob.prob_at_least_one(deck, copies, draws)
        else:
            p = prob.prob_at_least(deck, copies, draws, min_count)
        self._log_notice(
            f"[bold cyan]📊 Probabilidade:[/] "
            f"P(≥{min_count} de {copies} cópias em {draws} compras de {deck}) = {p:.1%}"
        )

    def _cmd_status(self, args: list[str]) -> None:
        """status — log completo do estado."""
        for side in ("A", "B"):
            p = self.game_state.players[side]
            self._log_notice(f"[bold]--- {HERO_LABELS.get(side, side)} ---[/]")
            self._log_notice(f"  Vida: {p.life}  AP: {p.action_points}  Pool: {p.pitch_pool}")
            self._log_notice(f"  Mão ({len(p.hand)}): {p.hand}")
            self._log_notice(f"  Arsenal: {p.arsenal}")
            self._log_notice(f"  Auras: {dict(p.auras)}")
            self._log_notice(f"  Graveyard: {p.graveyard}")
            self._log_notice(f"  Banished: {p.banished}")
            self._log_notice(f"  Equip destruídos: {p.equipment_destroyed}")
        self._log_notice(f"[bold]--- Chain ({len(self.game_state.chain)} links) ---[/]")
        for link in self.game_state.chain:
            resolved = "[resolvido]" if link.resolved else "[aberto]"
            self._log_notice(
                f"  {link.card_key}: {link.total_damage}{{p}} "
                f"(bloqueado {link.blocked_damage}, arcano {link.arcane_damage}) {resolved}"
            )

    def _cmd_clear(self, args: list[str]) -> None:
        """clear — limpa notificações."""
        self.notices.clear()
        self.query_one("#notices-log", RichLog).clear()

    # ── Helpers ──────────────────────────────────────────────────

    def _resolve_card(self, text: str) -> str:
        """Resolve texto para chave de carta; aceita parcial ou número da mão."""
        p = self.game_state.players[self.game_state.active_player]

        # Número da mão?
        if text.isdigit():
            idx = int(text) - 1
            if 0 <= idx < len(p.hand):
                return p.hand[idx]
            raise ValueError(f"Índice {text} fora da mão (1-{len(p.hand)})")

        # Nome exato ou parcial
        key = _find_card(text, self.cards)
        if key is None:
            raise ValueError(f"Carta não encontrada: '{text}'")
        return key


# ── Ponto de entrada ────────────────────────────────────────────────────


def launch(state: GameState | None = None, cards: dict[str, Card] | None = None) -> None:
    """Inicializa e roda a TUI."""

    cards = cards or load_cards()
    if state is None:
        state = new_game(BRIAR, ENIGMA, "A")
    app = FaBApp(state, cards)
    app.run()
