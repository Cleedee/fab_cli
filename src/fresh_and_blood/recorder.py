"""Gravador de sessão: log de decisões com snapshots do estado.

Cada entrada registra o comando executado, o estado antes da ação,
sugestões exibidas e o resultado. O log alimenta a revisão pós-jogo.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import GameState


@dataclass
class LogEntry:
    """Uma linha no histórico da partida."""

    timestamp: str
    turn: int
    active_player: str
    action: str  # draw, pitch, attack, defend, resolve, etc.
    description: str  # texto legível do que aconteceu
    state_snapshot: dict[str, Any]  # GameState.to_dict() no MOMENTO da ação
    suggestions: list[str] = field(default_factory=list)  # sugestões exibidas
    result: list[str] = field(default_factory=list)  # notices/resultados


@dataclass
class SessionLog:
    """Log completo de uma sessão."""

    hero_a: str
    hero_b: str
    start_time: str
    entries: list[LogEntry] = field(default_factory=list)

    def record(
        self,
        state: GameState,
        action: str,
        description: str,
        *,
        suggestions: list[str] | None = None,
        result: list[str] | None = None,
    ) -> LogEntry:
        """Adiciona uma entrada ao log com snapshot do estado atual."""
        entry = LogEntry(
            timestamp=datetime.now(UTC).isoformat(timespec="seconds"),
            turn=state.turn,
            active_player=state.active_player,
            action=action,
            description=description,
            state_snapshot=state.to_dict(),
            suggestions=suggestions or [],
            result=result or [],
        )
        self.entries.append(entry)
        return entry


# ── Save/Load ──────────────────────────────────────────────────────────


def save_session(log: SessionLog, path: str | Path) -> None:
    """Salva o log da sessão em JSON."""
    data = asdict(log)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_session(path: str | Path) -> SessionLog:
    """Carrega um log de sessão de JSON."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    entries = [LogEntry(**e) for e in data["entries"]]
    return SessionLog(
        hero_a=data["hero_a"],
        hero_b=data["hero_b"],
        start_time=data["start_time"],
        entries=entries,
    )


def find_logs(data_dir: str | Path = "data/logs") -> list[Path]:
    """Lista arquivos de log salvos."""
    p = Path(data_dir)
    if not p.exists():
        return []
    return sorted(p.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
