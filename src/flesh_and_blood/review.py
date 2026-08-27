"""Revisão pós-jogo e métricas de sessão.

Processa o SessionLog para extrair:
- Replay cronológico das decisões
- Métricas: dano por turno, cartas jogadas, taxa de lethal
- Alternativas que estavam disponíveis em cada ponto
"""

from __future__ import annotations

from dataclasses import dataclass

from .recorder import SessionLog


@dataclass
class SessionMetrics:
    """Métricas agregadas de uma sessão."""

    total_turns: int = 0
    total_attacks: int = 0
    total_defends: int = 0
    total_draws: int = 0
    total_pitches: int = 0
    total_arsenal: int = 0
    total_resolves: int = 0
    cards_played: int = 0
    lethal_missed: int = 0  # vezes que um plano letal foi ignorado
    damage_dealt_a: int = 0  # dano total causado por A
    damage_dealt_b: int = 0
    damage_taken_a: int = 0  # dano total recebido por A
    damage_taken_b: int = 0

    def to_lines(self) -> list[str]:
        """Linhas formatadas para exibição."""
        lines = [
            "[bold underline]📊 Métricas da Sessão[/]",
            f"  Turnos jogados: {self.total_turns}",
            f"  Ataques declarados: {self.total_attacks}",
            f"  Defesas: {self.total_defends}",
            f"  Compras: {self.total_draws}",
            f"  Pitches: {self.total_pitches}",
            f"  Resoluções: {self.total_resolves}",
            "",
            "[bold]Dano:[/]",
            f"  Briar (A) causou: {self.damage_dealt_a} — sofreu: {self.damage_taken_a}",
            f"  Enigma (B) causou: {self.damage_dealt_b} — sofreu: {self.damage_taken_b}",
            "",
        ]
        if self.lethal_missed:
            lines.append(f"[yellow]  Oportunidades letais perdidas: {self.lethal_missed}[/]")
        return lines


def compute_metrics(log: SessionLog) -> SessionMetrics:
    """Calcula métricas a partir do log da sessão."""
    m = SessionMetrics()

    for entry in log.entries:
        action = entry.action
        m.total_turns = max(m.total_turns, entry.turn)

        if action == "draw":
            m.total_draws += 1
        elif action == "pitch":
            m.total_pitches += 1
        elif action == "arsenal":
            m.total_arsenal += 1
        elif action == "play":
            m.cards_played += 1
        elif action in ("attack", "weapon"):
            m.total_attacks += 1
        elif action == "defend":
            m.total_defends += len(entry.description.split(",")) if entry.description else 1
        elif action == "resolve":
            m.total_resolves += 1
        elif action in ("boost", "arcane"):
            pass

    # Dano: infelizmente o snapshot puro não registra delta facilmente.
    # Estimamos pela diferença de vida entre entradas adjacentes.
    for i, entry in enumerate(log.entries):
        snap = entry.state_snapshot
        players = snap.get("players", {})
        for side, pstate in players.items():
            # Não temos o estado anterior aqui facilmente, então
            # estimamos aproximado pelo resumo textual do resolve.
            pass

    # Aproximação melhor: percorrer resolves e extrair dano do texto.
    for entry in log.entries:
        for r in entry.result:
            r_lower = r.lower()
            if "resolvido" in r_lower or "físico" in r_lower or "arcano" in r_lower:
                # Extrai números: "3{p} físico + 1{a} arcano"
                import re

                phys = 0
                arc = 0
                phys_m = re.search(r"(\d+)\{p\}", r)
                if phys_m:
                    phys = int(phys_m.group(1))
                arc_m = re.search(r"(\d+)\{a\}", r)
                if arc_m:
                    arc = int(arc_m.group(1))
                # Determina quem atacou
                prev_entry = None
                for j in range(log.entries.index(entry) - 1, -1, -1):
                    if log.entries[j].action in ("attack", "weapon"):
                        prev_entry = log.entries[j]
                        break
                if prev_entry:
                    attacker = prev_entry.active_player
                    if attacker == "A":
                        m.damage_dealt_a += phys + arc
                        m.damage_taken_b += phys + arc
                    else:
                        m.damage_dealt_b += phys + arc
                        m.damage_taken_a += phys + arc

    return m


def replay_summary(log: SessionLog, max_entries: int = 50) -> list[str]:
    """Gera um resumo textual do replay para exibição."""
    lines = []
    lines.append(f"[bold]📜 Replay — {log.hero_a} vs {log.hero_b}[/]")
    lines.append(f"Início: {log.start_time}  |  {len(log.entries)} ações registradas")
    lines.append("")

    for idx, entry in enumerate(log.entries):
        if idx >= max_entries:
            lines.append("[dim]... (mais entradas disponíveis)[/]")
            break
        side_label = "A" if entry.active_player == "A" else "B"
        ts = entry.timestamp[-8:]  # HH:MM:SS
        lines.append(
            f"  [dim]{ts}[/] T{entry.turn}[{side_label}] "
            f"[bold]{entry.action}[/] — {entry.description}"
        )
        if entry.suggestions:
            for s in entry.suggestions:
                lines.append(f"    [dim]💡 {s[:60]}[/]")
        if entry.result:
            for r in entry.result:
                lines.append(f"    [dim]→ {r[:80]}[/]")

    return lines
