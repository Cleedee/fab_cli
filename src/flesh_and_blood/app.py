"""Assistente de decisão FaB — TUI Textual (Fase 3).

Interface interativa no terminal para partidas Silver Age.
O usuário controla AMBOS os lados via comandos textuais.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Input, ListItem, ListView, RichLog, Static

from flesh_and_blood import attack as atk
from flesh_and_blood import combat as cmb
from flesh_and_blood import defense as dfs
from flesh_and_blood import probabilities as prob
from flesh_and_blood import recorder as rec
from flesh_and_blood import review as rvw
from flesh_and_blood.carddb import load_cards
from flesh_and_blood.models import (
    Card,
    GameState,
    Hero,
    new_game,
)

# ── Matchup ────────────────────────────────────────────────────────────

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DECK_DIR = DATA_DIR / "decks"
LOG_DIR = DATA_DIR / "logs"


@dataclass(frozen=True)
class Matchup:
    """Configuração da partida: heróis e armas de cada lado.

    Permite jogar com decks arbitrários; `weapon_*` são chaves das cartas
    (None se o deck não tem arma).
    """

    hero_a: Hero
    hero_b: Hero
    weapon_a: str | None = None
    weapon_b: str | None = None

    def hero(self, side: str) -> Hero:
        return self.hero_a if side == "A" else self.hero_b

    def label(self, side: str) -> str:
        return f"{self.hero(side).name} ({side})"

    def weapon_for(self, hero_key: str) -> str | None:
        return {self.hero_a.key: self.weapon_a, self.hero_b.key: self.weapon_b}.get(hero_key)


DEFAULT_MATCHUP = Matchup(
    hero_a=Hero(
        key="Briar, Warden of Thorns",
        name="Briar, Warden of Thorns",
        life=20,
        intellect=4,
        classes=("Runeblade",),
        talents=("Earth", "Lightning"),
    ),
    hero_b=Hero(
        key="Enigma",
        name="Enigma",
        life=20,
        intellect=4,
        classes=("Illusionist",),
        talents=("Mystic",),
    ),
    weapon_a="Star Fall",
    weapon_b="Cosmo, Scroll of Ancestral Tapestry",
)


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


def _parse_grave_source(args: list[str]) -> tuple[str, list[str]]:
    """Separa `from=graveyard` dos demais argumentos de play/attack.

    Retorna (origem, restante). Aceita from=graveyard ou from=grave; default hand.
    """
    source = "hand"
    rest: list[str] = []
    for a in args:
        if a.lower().startswith("from="):
            src = a.lower().split("=", 1)[1]
            if src not in ("hand", "grave", "graveyard"):
                raise ValueError(f"origem inválida: '{a}'")
            source = "graveyard" if src == "grave" else src
        else:
            rest.append(a)
    return source, rest


def _card_details(key: str, card: Card) -> list[str]:
    """Linhas com todos os detalhes de uma carta (para o log de notícias)."""
    lines: list[str] = []
    header = f"[bold cyan]🂠 {card.name}[/]"
    if card.color:
        header += f" [bold]({card.color.value})[/]"
    lines.append(header)

    meta: list[str] = []
    if card.types:
        meta.append(", ".join(card.types))
    if card.rarity:
        meta.append(f"[{card.rarity}]")
    lines.append("  [dim]" + " | ".join(meta) + "[/]")

    stats: list[str] = []
    if card.cost is not None:
        stats.append(f"Custo: {card.cost}{{r}}")
    if card.pitch is not None:
        stats.append(f"Pitch: {card.pitch}")
    if card.power is not None:
        stats.append(f"Poder: {card.power}{{p}}")
    if card.defense is not None:
        stats.append(f"Defesa: {card.defense}{{d}}")
    if stats:
        lines.append("  [bold]" + "  |  ".join(stats) + "[/]")

    if card.keywords:
        lines.append("  Keywords: " + ", ".join(card.keywords))

    if card.text:
        lines.append("  " + card.text.replace("\n", "\n  "))

    if not card.sa_legal:
        lines.append("  [red]Ilegal em Silver Age.[/]")
    return lines


# ── Board browser ────────────────────────────────────────────────────


@dataclass
class _BrowseCard:
    """Uma carta navegável no índice do board."""

    idx: int  # 1-based
    key: str
    side: str  # "A" ou "B"
    location: str  # "weapon", "equipment", "hand", "arsenal", "aura"
    label: str  # ex: "Wpn", "Head", "hand A", "Arsenal", "Aura"


def _entry_summary(entry: _BrowseCard, card: Card | None) -> str:
    """Linha resumida de uma carta (lista do modal)."""
    parts: list[str] = []
    if card is not None:
        if card.power is not None:
            parts.append(f"{card.power}{{p}}")
        if card.defense is not None:
            parts.append(f"{card.defense}{{d}}")
        if card.cost:
            parts.append(f"{card.cost}{{r}}")
        if card.keywords:
            parts.append(", ".join(card.keywords))
    txt = f"[{entry.idx}] [dim]{entry.label}:[/] [bold]{entry.key}[/]"
    if parts:
        txt += " — " + " — ".join(parts)
    return txt


def _collect_board_cards(state: GameState, cards: dict[str, Card]) -> list[_BrowseCard]:
    """Coleta todas as cartas visíveis na mesa e mãos com índices."""
    result: list[_BrowseCard] = []
    idx = 0

    for side in ("A", "B"):
        p = state.players[side]

        for key in p.weapons:
            idx += 1
            c = cards.get(key)
            slot = "2H" if c and "2H" in c.types else "1H"
            result.append(_BrowseCard(idx, key, side, "weapon", f"Wpn({slot})"))

        # Off-Hand: exibido na zona de armas (segundo slot)
        if p.offhand_key and p.offhand_key not in p.equipment_destroyed:
            idx += 1
            result.append(_BrowseCard(idx, p.offhand_key, side, "weapon", "Off-Hand"))

        for key in p.equipment_uses:
            if key in p.equipment_destroyed:
                continue
            if p.offhand_key and key == p.offhand_key:
                continue  # já listado na zona de armas
            idx += 1
            c = cards.get(key)
            slot = c.equipment_slot if c else "?"
            result.append(_BrowseCard(idx, key, side, "equipment", slot or "Equip"))

        for key in p.hand:
            idx += 1
            result.append(_BrowseCard(idx, key, side, "hand", f"Mão {side}"))

        if p.arsenal:
            idx += 1
            result.append(_BrowseCard(idx, p.arsenal, side, "arsenal", f"Arsenal {side}"))

        for key, counters in p.auras.items():
            for i, cnt in enumerate(counters):
                idx += 1
                label = f"Aura {side}" + (f" [{cnt}]" if cnt else "")
                result.append(_BrowseCard(idx, key, side, "aura", label))

        for key, copies in p.permanents.items():
            for i, cnt in enumerate(copies):
                idx += 1
                c = cards.get(key)
                sub = "Ally" if c and c.is_ally else "Item" if c and c.is_item else "Perm"
                label = f"{sub} {side}" + (f" [{cnt}]" if cnt else "")
                result.append(_BrowseCard(idx, key, side, "permanent", label))

        for name, qty in p.tokens.items():
            idx += 1
            result.append(_BrowseCard(idx, name, side, "token", f"Token {side} x{qty}"))

    return result


# ── Widgets ────────────────────────────────────────────────────────────


class PlayerPanel(Vertical):
    """Painel de um jogador: vida, mão, arsenal, recursos, auras."""

    DEFAULT_CSS = """
    PlayerPanel {
        border: solid $secondary;
        padding: 0 1;
        height: 100%;
        overflow-y: auto;
        overflow-x: hidden;
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
        yield Static(id=f"weapon-{self.side}")
        yield Static(id=f"hand-{self.side}")
        yield Static(id=f"arsenal-{self.side}")
        yield Static(id=f"perms-{self.side}")
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

        # Arma(s)
        weapon_lines = []
        for key in p.weapons:
            card = cards.get(key)
            if card:
                slot = "2H" if "2H" in card.types else "1H"
                txt = _card_display(key, card)
                weapon_lines.append(f"  {txt}  [dim]({slot})[/]")
            else:
                weapon_lines.append(f"  {key} [?]")
        # Off-Hand: exibido na zona de armas
        if p.offhand_key:
            card = cards.get(p.offhand_key)
            if card and p.offhand_key not in p.equipment_destroyed:
                txt = _card_display(p.offhand_key, card)
                weapon_lines.append(f"  {txt}  [dim](Off-Hand)[/]")
            elif p.offhand_key not in p.equipment_destroyed:
                weapon_lines.append(f"  {p.offhand_key} [?]")
        if not weapon_lines:
            weapon_lines.append(" (nenhuma)")
        self.query_one(f"#weapon-{self.side}", Static).update(
            "[bold]Arma(s):[/]\n" + "\n".join(weapon_lines)
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

        # Auras + tokens item
        aura_lines = []
        for key, copies in p.auras.items():
            for i, cnt in enumerate(copies):
                aura_lines.append(f"  {key} (+{cnt})")
        for name, qty in p.tokens.items():
            aura_lines.append(f"  {name} x{qty}")
        if not aura_lines:
            aura_lines.append(" (nenhum)")
        self.query_one(f"#auras-{self.side}", Static).update(
            "[bold]Auras/Tokens:[/]\n" + "\n".join(aura_lines)
        )

        # Permanentes (Ally/Item/Landmark) em jogo
        perm_lines = []
        for key, copies in p.permanents.items():
            for i, cnt in enumerate(copies):
                perm_lines.append(f"  {key}" + (f" (+{cnt})" if cnt else ""))
        if not perm_lines:
            perm_lines.append(" (nenhum)")
        self.query_one(f"#perms-{self.side}", Static).update(
            "[bold]Permanentes:[/]\n" + "\n".join(perm_lines)
        )

        # Equipamentos (exclui Off-Hand, que é exibido na zona de armas)
        eq_lines = []
        for key, uses in p.equipment_uses.items():
            if p.offhand_key and key == p.offhand_key:
                continue  # já listado na zona de armas
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


# ── Modal de cartas ────────────────────────────────────────────────


class _CardListItem(ListItem):
    """Item da ListView com referência à carta correspondente."""

    def __init__(self, entry: _BrowseCard, summary: str, **kwargs) -> None:
        super().__init__(Static(summary, markup=True), **kwargs)
        self.entry = entry


class CardBrowser(ModalScreen[None]):
    """Janela modal para navegar cartas (board) ou ver detalhes (read).

    Lista as cartas à esquerda com resumo (índice, seção, poder/defesa);
    detalhes completos à direita, atualizados ao navegar com as setas.
    Fecha com Esc ou q.
    """

    DEFAULT_CSS = """
    CardBrowser {
        align: center middle;
    }

    #browser-box {
        width: 92%;
        height: 92%;
        border: heavy $primary;
        background: $surface;
        padding: 0 1;
    }

    #browser-title {
        height: 3;
        content-align: left middle;
        text-style: bold;
    }

    #browser-hint {
        height: 1;
        color: $text-muted;
        content-align: center middle;
    }

    #browser-body {
        height: 1fr;
    }

    #browser-list-col {
        width: 42%;
        min-width: 34;
        border: round $secondary;
        margin: 0 1 0 0;
    }

    #browser-list {
        height: 1fr;
    }

    #browser-detail-col {
        width: 58%;
        min-width: 40;
        border: round $secondary;
        padding: 0 1;
        overflow-y: auto;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "dismiss", "Fechar", priority=True),
        Binding("q", "dismiss", "Fechar", priority=True),
    ]

    def __init__(
        self,
        entries: list[_BrowseCard],
        card_db: dict[str, Card],
        title: str = "Cartas",
        initial: int | None = None,
    ) -> None:
        super().__init__()
        self._entries = entries
        self._db = card_db
        self._title = title
        self._initial = initial

    def compose(self) -> ComposeResult:
        with Vertical(id="browser-box"):
            title = f"[bold]{self._title}[/]"
            if len(self._entries) > 1:
                title += f" — [{len(self._entries)} cartas]"
            yield Static(title, id="browser-title")
            with Horizontal(id="browser-body"):
                with Vertical(id="browser-list-col"):
                    yield ListView(id="browser-list")
                with Vertical(id="browser-detail-col"):
                    yield Static("", id="browser-details", markup=True)
            yield Static("↑/↓ navegar · Esc/q fechar", id="browser-hint")

    def on_mount(self) -> None:
        list_view = self.query_one("#browser-list", ListView)
        for entry in self._entries:
            list_view.append(_CardListItem(entry, _entry_summary(entry, self._db.get(entry.key))))
        if self._entries:
            list_view.index = self._initial if self._initial is not None else 0

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        item = event.item
        if isinstance(item, _CardListItem):
            self._show_details(item.entry)

    def _show_details(self, entry: _BrowseCard) -> None:
        details = self.query_one("#browser-details", Static)
        card = self._db.get(entry.key)
        if card is None:
            details.update(f"[red]Carta fora do registro: {entry.key}[/]")
            return
        pos = f"[dim]({entry.idx} · {entry.label})[/]"
        body = "\n".join(_card_details(entry.key, card))
        details.update(f"{pos}\n{body}")


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

    # Comandos que nao alteram estado (undo nao afeta)
    _READONLY_COMMANDS: ClassVar[frozenset[str]] = frozenset(
        {
            "",
            "board",
            "card",
            "help",
            "plan",
            "read",
            "suggest",
            "prob",
            "status",
            "clear",
            "log",
            "review",
            "metrics",
            "undo",
            "replay_next",
            "replay_prev",
            "replay_status",
            "replay_exit",
        }
    )

    # Estado reativo — incrementado apos cada mutacao
    version: reactive[int] = reactive(0)
    game_state: GameState
    cards: dict[str, Card]
    notices: list[str]
    session_log: rec.SessionLog
    _undo_stack: list[dict]

    def __init__(
        self,
        state: GameState,
        cards_dict: dict[str, Card],
        matchup: Matchup = DEFAULT_MATCHUP,
    ) -> None:
        super().__init__()
        self.game_state = state
        self.cards = cards_dict
        self.matchup = matchup
        self.notices = []
        self._undo_stack = []
        self._replay_index: int = 0
        self._replay_mode: bool = False
        self.session_log = rec.SessionLog(
            hero_a=matchup.hero_a.name,
            hero_b=matchup.hero_b.name,
            start_time=__import__("datetime").datetime.now().isoformat(timespec="seconds"),
        )

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="body"):
            yield PlayerPanel(
                "A",
                self.matchup.hero_a,
                self.matchup.label("A"),
                id="panel-a",
            )
            yield self._center_panel()
            yield PlayerPanel(
                "B",
                self.matchup.hero_b,
                self.matchup.label("B"),
                id="panel-b",
            )
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
        self._log_notice(
            f"{self.matchup.label('A')} vs {self.matchup.label('B')} — Turno 1. "
            "Comandos: [bold]help[/] para lista."
        )
        self._log_notice(
            "[dim]Não afiliado a Legend Story Studios. "
            "Flesh and Blood™ e nomes de produtos são marcas registradas da "
            "Legend Story Studios. Cartas, personagens e artes pertencem à "
            "Legend Story Studios.[/]"
        )
        p_a = self.game_state.players["A"]
        if p_a.hand or p_a.equipment_uses:
            self._log_notice(
                "[dim]Mão inicial e equipamentos já carregados. /help para comandos.[/]"
            )
        else:
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
        lbl = self.matchup.label(active)
        inp.placeholder = f"[{lbl}] Digite um comando (help para lista)..."

    # ── Processamento de comandos ─────────────────────────────────

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Processa um comando digitado."""
        raw = event.value.strip()
        if not raw:
            return
        inp = self.query_one("#command-input", Input)
        inp.clear()

        # Descobre se o comando altera estado para salvar snapshot
        parts = __import__("shlex").split(raw) if raw else []
        cmd = parts[0].lower() if parts else ""
        is_mutation = cmd not in self._READONLY_COMMANDS and cmd != ""
        if is_mutation:
            self._undo_stack.append(self.game_state.to_dict())

        try:
            self._exec(raw)
        except (cmb.CombatError, ValueError) as e:
            if is_mutation and self._undo_stack:
                self._undo_stack.pop()
            self._notify(f"Erro: {e}")
        except BaseException as e:
            if isinstance(e, (KeyboardInterrupt, SystemExit)):
                raise
            if is_mutation and self._undo_stack:
                self._undo_stack.pop()
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
            "board": self._cmd_board,
            "card": self._cmd_card,
            "draw": self._cmd_draw,
            "pitch": self._cmd_pitch,
            "discard": self._cmd_discard,
            "arsenal": self._cmd_arsenal,
            "token": self._cmd_token,
            "use": self._cmd_use,
            "play": self._cmd_play,
            "attack": self._cmd_attack,
            "weapon": self._cmd_weapon,
            "boost": self._cmd_boost,
            "arcane": self._cmd_arcane,
            "life": self._cmd_life,
            "defend": self._cmd_defend,
            "equip": self._cmd_equip,
            "resolve": self._cmd_resolve,
            "next": self._cmd_next,
            "switch": self._cmd_switch,
            "read": self._cmd_read,
            "plan": self._cmd_plan,
            "suggest": self._cmd_suggest,
            "prob": self._cmd_prob,
            "status": self._cmd_status,
            "clear": self._cmd_clear,
            "log": self._cmd_log,
            "save": self._cmd_save,
            "load": self._cmd_load,
            "review": self._cmd_review,
            "metrics": self._cmd_metrics,
            "replay": self._cmd_replay,
            "replay_next": self._cmd_replay_next,
            "replay_prev": self._cmd_replay_prev,
            "replay_status": self._cmd_replay_status,
            "replay_exit": self._cmd_replay_exit,
            "undo": self._cmd_undo,
            "reset": self._cmd_reset,
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
        self._log_notice("  [bold]board[/] [hand|field|a|b]  — navega cartas em janela modal")
        self._log_notice("  [bold]read[/] [carta|N]          — detalhes de uma carta (modal)")
        self._log_notice("  [bold]card[/] <carta>            — mostra detalhes da carta")
        self._log_notice("  [bold]draw[/] <carta>           — adiciona carta à mão do ativo")
        self._log_notice("  [bold]pitch[/] <carta>          — dá pitch de uma carta da mão")
        self._log_notice("  [bold]discard[/] <carta>        — descarta carta da mão")
        self._log_notice("  [bold]arsenal[/] <carta>        — coloca carta no arsenal")
        self._log_notice("  [bold]token[/] <nome> [qtd]     — cria token/aura/permanente")
        self._log_notice("  [bold]token remove[/] <nome>    — remove token")
        self._log_notice("  [bold]use[/] <token>             — ativa item (Gold/Silver/Copper)")
        self._log_notice("  [bold]play[/] <carta> [from=graveyard] — joga non-attack action")
        self._log_notice("  [bold]attack[/] <carta> [dominate=1] [from=graveyard] — ataca")
        self._log_notice("  [bold]weapon[/] [1|2]            — ataca com a arma (índice)")
        self._log_notice("  [bold]boost[/] <N>               — +N{p} no link atual")
        self._log_notice("  [bold]arcane[/] <N>              — +N arcano no link atual")
        self._log_notice("  [bold]life[/] <±N> [a|b]          — ajusta vida (ex.: life -4)")
        self._log_notice("  [bold]defend[/] [auto|N|suggest] — bloqueia link oponente")
        self._log_notice("  [bold]equip[/] <equip>           — usa equipamento p/ defesa")
        self._log_notice("  [bold]resolve[/] [ward=N] [arcane=N] — resolve link")
        self._log_notice("  [bold]next[/]                    — encerra turno / avança")
        self._log_notice("  [bold]switch[/]                  — troca jogador ativo")
        self._log_notice("  [bold]plan[/]                    — sugere linha de ataque")
        self._log_notice("  [bold]suggest[/]                 — sugere bloqueio")
        self._log_notice("  [bold]prob[/] <copias> <deck> <compras> [min] — probabilidade")
        self._log_notice("  [bold]status[/]                  — estado completo")
        self._log_notice("  [bold]clear[/]                   — limpa notificações")
        self._log_notice("  [bold]log[/]                     — exibe histórico da sessão")
        self._log_notice("  [bold]save[/] [nome]             — salva o log em data/logs/")
        self._log_notice("  [bold]load[/] [nome]             — carrega sessão anterior")
        self._log_notice("  [bold]review[/]                  — visão geral do replay")
        self._log_notice("  [bold]metrics[/]                 — estatísticas da sessão")
        self._log_notice(
            "  [bold]replay[/] [N]              — entra no modo replay (passo a passo)"
        )
        self._log_notice("  [bold]replay_next[/]             — próxima entrada do replay")
        self._log_notice("  [bold]replay_prev[/]             — entrada anterior do replay")
        self._log_notice("  [bold]replay_status[/]           — estado completo da entrada atual")
        self._log_notice("  [bold]replay_exit[/]             — sai do modo replay")
        self._log_notice("  [bold]undo[/]                    — desfaz a última ação")
        self._log_notice("  [bold]reset[/]                   — reinicia a partida do zero")
        self._log_notice("  [bold]help[/]                    — esta mensagem")

    def _open_board_modal(self, args: list[str]) -> None:
        """Abre o modal do board com filtros opcionais (hand/field/a/b)."""
        all_cards = _collect_board_cards(self.game_state, self.cards)
        if not all_cards:
            self._log_notice("Nenhuma carta na mesa ou nas mãos.")
            return

        filtros = {a.lower() for a in args}
        hand_only = "hand" in filtros
        field_only = "field" in filtros
        side_filter: str | None = None
        if "a" in filtros:
            side_filter = "A"
        elif "b" in filtros:
            side_filter = "B"

        filtered = all_cards
        if hand_only:
            filtered = [c for c in filtered if c.location == "hand"]
        elif field_only:
            filtered = [c for c in filtered if c.location != "hand"]
        if side_filter:
            filtered = [c for c in filtered if c.side == side_filter]

        if not filtered:
            self._log_notice("Nenhuma carta corresponde ao filtro.")
            return

        self.push_screen(
            CardBrowser(filtered, self.cards, title=f"Board — {len(filtered)} carta(s)")
        )

    def _cmd_board(self, args: list[str]) -> None:
        """board [filtro] — abre janela modal com cartas na mesa e mãos.

        Filtros: hand, field, a, b (combináveis).
        Exemplos: board hand, board a, board field b
        """
        self._open_board_modal(args)

    def _cmd_read(self, args: list[str]) -> None:
        """read [carta|N] — abre detalhes de uma carta em janela modal.

        read            — abre o board completo em modal
        read <carta>    — busca por nome no registro e abre detalhes
        read <N>        — carta N da mão do jogador ativo
        """
        if not args:
            self._open_board_modal([])
            return

        texto = " ".join(args)
        side = self.game_state.active_player
        key: str | None = None
        if texto.isdigit():
            p = self.game_state.players[side]
            idx = int(texto) - 1
            if 0 <= idx < len(p.hand):
                key = p.hand[idx]
            else:
                raise ValueError(f"Índice {texto} fora da mão (1-{len(p.hand)})")
        else:
            key = _find_card(texto, self.cards)
        if key is None:
            raise ValueError(f"Carta não encontrada: '{texto}'")
        if key not in self.cards:
            raise ValueError(f"Carta fora do registro: {key}")

        entry = _BrowseCard(1, key, side, "read", "Carta")
        self.push_screen(CardBrowser([entry], self.cards, title=key))

    def _cmd_card(self, args: list[str]) -> None:
        """card <carta|número> — mostra todos os detalhes de uma carta.

        Aceita nome parcial ("Snatch", "Unmovable (blue)") ou o número da
        carta na mão do jogador ativo ("1", "2").
        """
        if not args:
            raise ValueError("uso: card <carta ou número da mão>")
        texto = " ".join(args)

        key: str | None = None
        if texto.isdigit():
            p = self.game_state.players[self.game_state.active_player]
            idx = int(texto) - 1
            if 0 <= idx < len(p.hand):
                key = p.hand[idx]
            else:
                raise ValueError(f"Índice {texto} fora da mão (1-{len(p.hand)})")
        else:
            key = _find_card(texto, self.cards)
        if key is None:
            raise ValueError(f"Carta não encontrada: '{texto}'")

        card = self.cards.get(key)
        if card is None:
            raise ValueError(f"Carta fora do registro: {key}")
        for line in _card_details(key, card):
            self._log_notice(line)

    def _cmd_draw(self, args: list[str]) -> None:
        """draw <carta> — adiciona à mão do jogador ativo."""
        if not args:
            raise ValueError("uso: draw <carta>")
        key = self._resolve_card(" ".join(args))
        p = self.game_state.players[self.game_state.active_player]
        p.hand.append(key)
        self._log_notice(f"{self.game_state.active_player} comprou: {key}")
        self._record("draw", f"{self.game_state.active_player} comprou {key}")

    def _cmd_pitch(self, args: list[str]) -> None:
        """pitch <carta> — dá pitch da mão."""
        if not args:
            raise ValueError("uso: pitch <carta>")
        key = self._resolve_card(" ".join(args))
        val = cmb.pitch(self.game_state, self.game_state.active_player, key, self.cards)
        self._log_notice(f"{key} pichada: +{val}{{r}}")
        self._record("pitch", f"{key} → +{val}{{r}}")

    def _cmd_discard(self, args: list[str]) -> None:
        """discard <carta> — descarta carta da mão para o cemitério."""
        if not args:
            raise ValueError("uso: discard <carta>")
        key = self._resolve_card(" ".join(args))
        cmb.discard(self.game_state, self.game_state.active_player, key, self.cards)
        self._log_notice(f"{key} descartada.")
        self._record("discard", f"{key} → cemitério")

    def _cmd_token(self, args: list[str]) -> None:
        """token <nome> [qtd] — cria token; token remove <nome> [qtd] — remove."""
        if not args:
            raise ValueError("uso: token <nome> [qtd] ou token remove <nome> [qtd]")
        if args[0] == "remove":
            if len(args) < 2:
                raise ValueError("uso: token remove <nome> [qtd]")
            name = " ".join(args[1:-1]) if args[-1].isdigit() else " ".join(args[1:])
            qty = int(args[-1]) if args[-1].isdigit() else 1
            name = self._resolve_permanent_name(name)
            notice = cmb.remove_token(self.game_state, self.game_state.active_player, name, qty)
        else:
            name = " ".join(args[:-1]) if args[-1].isdigit() else " ".join(args)
            qty = int(args[-1]) if args[-1].isdigit() else 1
            name = self._resolve_permanent_name(name)
            notice = cmb.create_token(
                self.game_state, self.game_state.active_player, name, qty, self.cards
            )
        self._log_notice(f"🎯 {notice.text}")
        self._record("token", notice.text)

    def _cmd_use(self, args: list[str]) -> None:
        """use <token> — ativa item token (Gold/Silver/Copper)."""
        if not args:
            raise ValueError("uso: use <token> (Gold, Silver, Copper)")
        name = " ".join(args)
        notice = cmb.use_item_token(
            self.game_state, self.game_state.active_player, name, self.cards
        )
        self._log_notice(f"🎯 {notice.text}")
        self._record("use", notice.text)

    def _cmd_life(self, args: list[str]) -> None:
        """life <±N> [a|b] — ajusta a vida de um jogador manualmente.

        Delta com sinal: negativo tira, positivo soma. Lado opcional
        (a/b), default o jogador ativo. Ex.: life -4, life B +2.
        """
        if not args:
            raise ValueError("uso: life <±N> [a|b] (ex.: life -4, life b +2)")
        delta_arg: str | None = None
        side_arg: str | None = None
        delta_args = [a for a in args if a.lower() not in ("a", "b")]
        side_args = [a for a in args if a.lower() in ("a", "b")]
        if len(delta_args) != 1 or len(side_args) > 1:
            raise ValueError("uso: life <±N> [a|b] (ex.: life -4, life b +2)")
        delta_arg = delta_args[0]
        side_arg = side_args[0] if side_args else None
        raw = delta_arg[1:] if delta_arg[:1] in "+-" else delta_arg
        if not raw.isdigit():
            raise ValueError(f"delta inválido: '{delta_arg}' (use ex.: -4, +2)")
        delta = int(delta_arg)
        side = side_arg.upper() if side_arg else self.game_state.active_player
        notice = cmb.adjust_life(self.game_state, side, delta)
        self._log_notice(f"❤️ {notice.text}")
        self._record("life", notice.text)

    def _cmd_arsenal(self, args: list[str]) -> None:
        """arsenal <carta> — coloca no arsenal."""
        if not args:
            raise ValueError("uso: arsenal <carta>")
        key = self._resolve_card(" ".join(args))
        cmb.place_arsenal(self.game_state, self.game_state.active_player, key)
        self._log_notice(f"{key} colocada no arsenal.")
        self._record("arsenal", f"{key} → arsenal")

    def _cmd_play(self, args: list[str]) -> None:
        """play <carta> [from=graveyard] — joga non-attack action."""
        source, card_args = _parse_grave_source(args)
        if not card_args:
            raise ValueError("uso: play <carta> [from=graveyard]")
        key = self._resolve_card(" ".join(card_args))
        notices = cmb.play_action(
            self.game_state, self.game_state.active_player, key, self.cards, source=source
        )
        for n in notices:
            self._log_notice(f"⚡ {n.text}")
        self._record("play", f"Jogou {key} ({source})", result=[n.text for n in notices])

    def _cmd_attack(self, args: list[str]) -> None:
        """attack <carta> [dominate=1] [from=graveyard] — declara ataque."""
        if not args:
            raise ValueError("uso: attack <carta> [dominate=1] [from=graveyard]")
        dominate = False
        card_args = [a for a in args if "dominate" not in a.lower()]
        for a in args:
            if "dominate" in a.lower():
                dominate = True
        source, card_args = _parse_grave_source(card_args)
        if not card_args:
            raise ValueError("uso: attack <carta> [dominate=1] [from=graveyard]")
        key = self._resolve_card(" ".join(card_args))
        link = cmb.declare_attack(
            self.game_state,
            self.game_state.active_player,
            key,
            self.cards,
            dominate=dominate,
            source=source,
        )
        dom_str = " [yellow]Dominate[/]" if dominate else ""
        self._log_notice(f"⚔ Ataque declarado: {key} ({link.total_damage}{{p}}){dom_str}")
        if source == "graveyard":
            self._log_notice("[dim]Ataque do cemitério (watery grave).[/]")
        self._record(
            "attack",
            f"{key} ({link.total_damage}{{p}}){dom_str} ({source})",
        )

    def _cmd_weapon(self, args: list[str]) -> None:
        """weapon [1|2] — ataca com a arma (1 ou 2 para escolher, se houver mais de uma)."""
        p = self.game_state.players[self.game_state.active_player]
        if not p.weapons:
            raise cmb.CombatError("Nenhuma arma equipada.")
        idx = 0
        if args and args[0].isdigit():
            idx = int(args[0]) - 1
        if idx < 0 or idx >= len(p.weapons):
            raise cmb.CombatError(f"Índice de arma inválido. Use 1-{len(p.weapons)}")
        weapon_key = p.weapons[idx]
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
        self._record("weapon", f"{weapon_key} ({link.total_damage}{{p}})")

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
        """defend [auto|N|suggest] ou defend <carta> [carta ...] — bloqueia link.

        Modes:
          defend           — abre Sugestão #1 automaticamente
          defend auto      — aplica melhor sugestão (cartas + equipamento)
          defend N         — aplica sugestão #N
          defend suggest   — mostra sugestões (igual ao comando suggest)
          defend <carta>   — bloqueia com cartas da mão (comportamento original)
        """
        attacker = self.game_state.active_player
        defender = self.game_state.opponent_of(attacker)
        link = cmb.current_link(self.game_state, attacker)

        if not args:
            # Sem argumentos: aplica sugestão #1 automaticamente
            if link is None:
                self._log_notice("[yellow]Nenhum ataque ativo para defender.[/]")
                return
            self._apply_defense_suggestion(defender, link, 1)
            return

        arg = args[0].lower()

        if arg == "suggest":
            self._cmd_suggest([])
            return

        if arg == "auto":
            if link is None:
                self._log_notice("[yellow]Nenhum ataque ativo para defender.[/]")
                return
            self._apply_defense_suggestion(defender, link, 1)
            return

        if arg.isdigit():
            if link is None:
                self._log_notice("[yellow]Nenhum ataque ativo para defender.[/]")
                return
            self._apply_defense_suggestion(defender, link, int(arg))
            return

        # Modo original: defend <carta> [carta ...]
        keys = []
        for a in args:
            key = self._resolve_card(a, side=defender)
            keys.append(key)
        notices = cmb.defend_link(self.game_state, defender, keys, self.cards)
        for n in notices:
            self._log_notice(f"🛡 {n.text}")
        self._record(
            "defend",
            f"Defendeu com {', '.join(keys)}",
            result=[n.text for n in notices],
        )

    def _apply_defense_suggestion(self, defender: str, link, suggestion_index: int) -> None:
        """Aplica uma sugestão de defesa por índice (1-based)."""
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
            top=5,
            earth_bonus=earth_bonus,
        )
        if not opts:
            self._log_notice("[yellow]Nenhuma opção de defesa disponível.[/]")
            return
        idx = suggestion_index - 1
        if idx >= len(opts):
            self._log_notice(
                f"[yellow]Sugestão #{suggestion_index} não existe (máximo: {len(opts)}).[/]"
            )
            return
        opt = opts[idx]

        # Aplica cartas da mão
        if opt.hand_cards:
            notices = cmb.defend_link(self.game_state, defender, list(opt.hand_cards), self.cards)
            for n in notices:
                self._log_notice(f"🛡 {n.text}")
            self._record(
                "defend",
                f"Defendeu com {', '.join(opt.hand_cards)}",
                result=[n.text for n in notices],
            )

        # Aplica equipamentos
        for eq_key in opt.equipment:
            gained = cmb.use_equipment_defense(self.game_state, defender, eq_key, self.cards)
            self._log_notice(f"🛡 Equipamento {eq_key}: +{gained} de bloqueio.")
            self._record("equip", f"{eq_key}: +{gained} de bloqueio")

        hand_str = ", ".join(opt.hand_cards) if opt.hand_cards else "(nenhuma)"
        equip_str = ", ".join(opt.equipment) if opt.equipment else "(nenhum)"
        self._log_notice(
            f"  [bold]Sugestão #{suggestion_index}:[/] "
            f"Mão: {hand_str}  Equip: {equip_str}  "
            f"Bloqueio: {opt.block_total}  Dano: {opt.damage_taken}"
        )

    def _cmd_equip(self, args: list[str]) -> None:
        """equip <nome> — usa equipamento para defesa."""
        if not args:
            raise ValueError("uso: equip <nome>")
        defender = self.game_state.opponent_of(self.game_state.active_player)
        key = self._resolve_card(" ".join(args), side=defender)
        gained = cmb.use_equipment_defense(self.game_state, defender, key, self.cards)
        self._log_notice(f"🛡 Equipamento {key}: +{gained} de bloqueio.")
        self._record("equip", f"{key}: +{gained} de bloqueio")

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
        hit_str = "[red]ACERTOU[/]" if result["hit"] else "[blue]BLOQUEADO[/]"
        self._log_notice(
            f"💥 Resolvido: {result['physical']}{{p}} físico + {result['arcane']}{{a}} arcano"
            f" → {hit_str}"
        )
        for n in result["notices"]:
            self._log_notice(f"⚡ {n.text}")
        self._record(
            "resolve",
            f"{result['physical']}{{p}} + {result['arcane']}{{a}} → {'acertou' if result['hit'] else 'bloqueado'}",
            result=[n.text for n in result["notices"]],
        )

    def _cmd_next(self, args: list[str]) -> None:
        """next — encerra o turno do ativo e inicia o do oponente."""
        end_notices = cmb.end_turn(self.game_state)
        for n in end_notices:
            self._log_notice(f"⚡ {n.text}")
        new_active = self.game_state.active_player
        notices = cmb.start_turn(self.game_state, new_active)
        self._log_notice(
            f"⏭ Turno {self.game_state.turn} — agora joga {self.matchup.label(new_active)}"
        )
        for n in notices:
            self._log_notice(f"⚡ {n.text}")
        self._record(
            "next",
            f"Turno {self.game_state.turn} → {self.matchup.label(new_active)}",
        )

    def _cmd_switch(self, args: list[str]) -> None:
        """switch — troca o lado 'ativo' (quem ataca/age)."""
        cur = self.game_state.active_player
        new = "B" if cur == "A" else "A"
        self.game_state.active_player = new
        self._log_notice(f"🔄 Lado ativo: {self.matchup.label(new)}")
        self._record("switch", f"Ativo: {self.matchup.label(new)}")

    def _cmd_plan(self, args: list[str]) -> None:
        """plan — mostra sugestão de linha de ataque."""
        side = self.game_state.active_player
        me = self.game_state.players[side]
        weapon_key = me.weapons[0] if me.weapons else None
        opp = self.game_state.opponent_of(side)
        opp_life = self.game_state.players[opp].life

        plan = atk.plan_attack(
            self.game_state,
            side,
            self.cards,
            opponent_life=opp_life,
            weapon_key=weapon_key,
        )
        self._log_notice(
            f"[bold cyan]📋 Plano de ataque:[/] {self.matchup.label(side)} "
            f"(AP {me.action_points}, pool {me.pitch_pool}{{r}})"
        )
        if me.action_points <= 0:
            self._log_notice(
                "[yellow]  Sem action points — use [bold]next[/] para virar o turno "
                "ou [bold]switch[/] para o outro lado.[/]"
            )
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
        if plan.arsenal_suggestion:
            self._log_notice(f"  Arsenal: [bold]{plan.arsenal_suggestion}[/]")
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
            eff_str = "inf" if opt.efficiency == float("inf") else f"{opt.efficiency:.1f}"
            self._log_notice(
                f"  {i}. "
                f"Mão: {hand_str}  "
                f"Equip: {equip_str}  "
                f"Bloqueio: {opt.block_total}  "
                f"Dano: {opt.damage_taken}  "
                f"Valor: {opt.value_lost:.1f}  "
                f"Eficiência: {eff_str}  "
                f"Ciclo: {opt.cycle_score:.1f}"
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
            self._log_notice(f"[bold]--- {self.matchup.label(side)} ---[/]")
            self._log_notice(f"  Vida: {p.life}  AP: {p.action_points}  Pool: {p.pitch_pool}")
            self._log_notice(f"  Mão ({len(p.hand)}): {p.hand}")
            self._log_notice(f"  Arsenal: {p.arsenal}")
            self._log_notice(f"  Auras: {dict(p.auras)}")
            self._log_notice(f"  Permanentes: {dict(p.permanents)}")
            self._log_notice(f"  Tokens: {dict(p.tokens)}")
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

    def _cmd_undo(self, args: list[str]) -> None:
        """undo — desfaz a última ação que alterou o estado."""
        if not self._undo_stack:
            raise ValueError("Nada para desfazer.")
        prev = self._undo_stack.pop()
        self.game_state = GameState.from_dict(prev)
        # Remove última entrada do log da sessão
        if self.session_log.entries:
            self.session_log.entries.pop()
        self._log_notice("[yellow]↩ Desfeito: estado anterior restaurado.[/]")

    def _cmd_reset(self, args: list[str]) -> None:
        """reset — reinicia a partida do zero (limpa todo o estado)."""
        # Salva snapshot caso queira desfazer o reset
        self._undo_stack.append(self.game_state.to_dict())
        self.game_state = new_game(self.matchup.hero_a, self.matchup.hero_b, "A")
        self.notices.clear()
        self.query_one("#notices-log", RichLog).clear()
        # Reinicia o log da sessão
        self.session_log.entries.clear()
        self._log_notice("[bold green]🔄 Partida reiniciada![/]")
        self._log_notice(f"{self.matchup.label('A')} vs {self.matchup.label('B')} — Turno 1.")

    # ── Comandos da Fase 4 ────────────────────────────────────

    def _cmd_log(self, args: list[str]) -> None:
        """log — exibe o histórico da sessão."""
        lines = rvw.replay_summary(self.session_log, max_entries=60)
        for line in lines:
            self._log_notice(line)

    def _cmd_save(self, args: list[str]) -> None:
        """save [nome] — salva o log da sessão."""
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        nome = (
            " ".join(args)
            if args
            else f"sessao_{self.session_log.start_time[:19].replace(':', '-')}"
        )
        path = LOG_DIR / f"{nome}.json"
        rec.save_session(self.session_log, path)
        self._log_notice(f"💾 Sessão salva em: [bold]{path.name}[/]")

    def _cmd_load(self, args: list[str]) -> None:
        """load [nome] — carrega sessão anterior."""
        if args:
            nome = " ".join(args)
            path = LOG_DIR / f"{nome}.json"
            if not path.exists():
                candidates = list(LOG_DIR.glob(f"{nome}*.json"))
                if not candidates:
                    raise ValueError(f"Arquivo não encontrado: {nome}.json")
                path = candidates[0]
        else:
            logs = rec.find_logs(LOG_DIR)
            if not logs:
                raise ValueError("Nenhum log salvo encontrado.")
            path = logs[0]

        loaded = rec.load_session(path)
        self._restore_session(loaded)

        self._log_notice(f"[bold cyan]📂 Sessão carregada: {path.name}[/]")
        lines = rvw.replay_summary(loaded, max_entries=30)
        for line in lines:
            self._log_notice(line)

    def _cmd_review(self, args: list[str]) -> None:
        """review — visão geral do replay."""
        lines = rvw.replay_summary(self.session_log)
        for line in lines:
            self._log_notice(line)

    def _cmd_metrics(self, args: list[str]) -> None:
        """metrics — estatísticas da sessão atual."""
        m = rvw.compute_metrics(self.session_log)
        for line in m.to_lines():
            self._log_notice(line)

    # ── Replay interativo ───────────────────────────────────────

    def _cmd_replay(self, args: list[str]) -> None:
        """replay [N] — entra no modo replay ou pula para a entrada N."""
        if not self.session_log.entries:
            self._log_notice("[yellow]Nenhuma ação registrada para replay.[/]")
            return
        if args and args[0].isdigit():
            idx = int(args[0]) - 1
            if 0 <= idx < len(self.session_log.entries):
                self._replay_index = idx
                self._replay_mode = True
                self._show_replay_entry()
            else:
                self._log_notice(
                    f"[yellow]Índice {args[0]} fora do intervalo "
                    f"(1-{len(self.session_log.entries)}).[/]"
                )
        else:
            self._replay_index = 0
            self._replay_mode = True
            self._log_notice(f"[bold]🎬 Modo Replay — {len(self.session_log.entries)} ações[/]")
            self._log_notice(
                "[dim]Comandos: replay_next, replay_prev, replay_status, replay_exit[/]"
            )
            self._show_replay_entry()

    def _cmd_replay_next(self, args: list[str]) -> None:
        """replay_next — avança para a próxima entrada do replay."""
        if not self._replay_mode:
            self._log_notice("[yellow]Use 'replay' para entrar no modo replay.[/]")
            return
        if self._replay_index < len(self.session_log.entries) - 1:
            self._replay_index += 1
            self._show_replay_entry()
        else:
            self._log_notice("[dim]Fim do replay.[/]")

    def _cmd_replay_prev(self, args: list[str]) -> None:
        """replay_prev — volta para a entrada anterior do replay."""
        if not self._replay_mode:
            self._log_notice("[yellow]Use 'replay' para entrar no modo replay.[/]")
            return
        if self._replay_index > 0:
            self._replay_index -= 1
            self._show_replay_entry()
        else:
            self._log_notice("[dim]Início do replay.[/]")

    def _cmd_replay_status(self, args: list[str]) -> None:
        """replay_status — mostra estado completo da entrada atual."""
        if not self._replay_mode:
            self._log_notice("[yellow]Use 'replay' para entrar no modo replay.[/]")
            return
        if not self.session_log.entries:
            return
        entry = self.session_log.entries[self._replay_index]
        self._log_notice(
            f"[bold]--- Estado na entrada {self._replay_index + 1}/"
            f"{len(self.session_log.entries)} ---[/]"
        )
        self._log_notice(
            f"  Turno: {entry.turn}  |  Lado: {entry.active_player}  |  Ação: {entry.action}"
        )
        self._log_notice(f"  Descrição: {entry.description}")
        if entry.suggestions:
            for s in entry.suggestions:
                self._log_notice(f"  [dim]💡 {s}[/]")
        if entry.result:
            for r in entry.result:
                self._log_notice(f"  [dim]→ {r}[/]")
        # Mostra resumo do estado
        try:
            snap = GameState.from_dict(entry.state_snapshot)
            for side in ("A", "B"):
                p = snap.players[side]
                self._log_notice(
                    f"  {side}: vida={p.life} AP={p.action_points} mão={len(p.hand)} cartas"
                )
        except (KeyError, TypeError, ValueError):
            self._log_notice("  [dim](snapshot indisponível)[/]")

    def _cmd_replay_exit(self, args: list[str]) -> None:
        """replay_exit — sai do modo replay."""
        self._replay_mode = False
        self._log_notice("[dim]Saiu do modo replay.[/]")

    def _show_replay_entry(self) -> None:
        """Exibe a entrada atual do replay."""
        entry = self.session_log.entries[self._replay_index]
        ts = entry.timestamp[-8:]
        side_label = entry.active_player
        self._log_notice(
            f"[bold]▶ [{self._replay_index + 1}/{len(self.session_log.entries)}][/] "
            f"[dim]{ts}[/] T{entry.turn}[{side_label}] "
            f"[bold]{entry.action}[/] — {entry.description}"
        )
        if entry.suggestions:
            for s in entry.suggestions:
                self._log_notice(f"  [dim]💡 {s}[/]")
        if entry.result:
            for r in entry.result:
                self._log_notice(f"  [dim]→ {r}[/]")

    # ── Helpers ──────────────────────────────────────────────────

    def _restore_session(self, loaded: rec.SessionLog) -> None:
        """Restaura game_state e session_log a partir de um log carregado.

        Usa o snapshot da última ação registrada; sem isso, levanta erro.
        Não depende da UI, então é testável isoladamente.
        """
        if not loaded.entries:
            raise ValueError("Sessão não contém ações para restaurar.")
        last_snapshot = loaded.entries[-1].state_snapshot
        try:
            self.game_state = GameState.from_dict(last_snapshot)
        except (KeyError, TypeError, ValueError) as e:
            raise ValueError(f"Snapshot da sessão inválido: {e}")
        self.session_log = loaded
        self._undo_stack.clear()
        self.notices.clear()

    def _resolve_card(self, text: str, side: str | None = None) -> str:
        """Resolve texto para chave de carta; aceita parcial ou número da mão.

        `side`: se informado, busca na mão desse jogador (ex.: defensor).
        Padrão: jogador ativo.
        """
        side = side or self.game_state.active_player
        p = self.game_state.players[side]

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

    def _resolve_permanent_name(self, name: str) -> str:
        """Resolve nome parcial de permanente (ex.: "Riggermortis" → "Riggermortis (yellow)").

        Se o texto não corresponder a uma carta permanente, devolve o nome
        original (mantém o fluxo de tokens/auras).
        """
        key = _find_card(name, self.cards)
        if key is not None and self.cards[key].is_permanent:
            return key
        return name


# ── Ponto de entrada ────────────────────────────────────────────────────


def launch(
    state: GameState | None = None,
    cards: dict[str, Card] | None = None,
    matchup: Matchup = DEFAULT_MATCHUP,
) -> None:
    """Inicializa e roda a TUI."""
    cards = cards or load_cards()
    if state is None:
        state = new_game(matchup.hero_a, matchup.hero_b, "A")
    app = FaBApp(state, cards, matchup=matchup)
    app.run()
