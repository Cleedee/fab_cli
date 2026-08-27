"""Testes do gravador de sessão e revisão pós-jogo."""

import pytest

from flesh_and_blood.models import GameState, Hero, new_game
from flesh_and_blood.recorder import SessionLog, find_logs, load_session, save_session
from flesh_and_blood.review import compute_metrics, replay_summary

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


@pytest.fixture
def state():
    return new_game(BRIAR, ENIGMA, "A")


@pytest.fixture
def session(state):
    return SessionLog(hero_a="Briar", hero_b="Enigma", start_time="2026-01-01T00:00:00")


def test_cria_log_vazio(session):
    assert len(session.entries) == 0
    assert session.hero_a == "Briar"


def test_registra_entrada(session, state):
    entry = session.record(state, action="draw", description="Snatch (red)")
    assert entry.action == "draw"
    assert entry.description == "Snatch (red)"
    assert entry.turn == 1
    assert entry.active_player == "A"
    assert len(session.entries) == 1


def test_registra_sugestoes(session, state):
    entry = session.record(
        state,
        action="suggest",
        description="Top 3 defesas",
        suggestions=["1. Mão: Snatch | Dano: 0", "2. Mão: (nenhuma) | Dano: 4"],
    )
    assert len(entry.suggestions) == 2
    assert "Snatch" in entry.suggestions[0]


def test_save_load_redondo(session, state, tmp_path):
    session.record(state, action="draw", description="Snatch (red)")
    session.record(state, action="draw", description="Sizzle (red)")
    path = tmp_path / "teste.json"
    save_session(session, path)
    assert path.exists()

    loaded = load_session(path)
    assert loaded.hero_a == "Briar"
    assert len(loaded.entries) == 2
    assert loaded.entries[0].description == "Snatch (red)"


def test_save_load_com_sugestoes(session, state, tmp_path):
    session.record(
        state,
        action="suggest",
        description="teste",
        suggestions=["opcao 1", "opcao 2"],
        result=["nota 1"],
    )
    path = tmp_path / "completo.json"
    save_session(session, path)

    loaded = load_session(path)
    assert loaded.entries[0].suggestions == ["opcao 1", "opcao 2"]
    assert loaded.entries[0].result == ["nota 1"]


def test_find_logs_vazio():
    logs = find_logs("/tmp/nao-existe")
    assert logs == []


def test_find_logs_com_arquivos(session, state, tmp_path):
    path = tmp_path / "teste.json"
    save_session(session, path)
    logs = find_logs(str(tmp_path))
    assert len(logs) == 1
    assert logs[0].name == "teste.json"


def test_metrics_simples(session, state):
    session.record(state, action="draw", description="Snatch (red)")
    session.record(state, action="attack", description="Snatch (red) (4{p})")
    session.record(
        state,
        action="resolve",
        description="3{p} físico + 1{a} arcano",
        result=["On-hit de Snatch: conferir efeitos."],
    )
    m = compute_metrics(session)
    assert m.total_draws == 1
    assert m.total_attacks == 1
    assert m.total_resolves == 1


def test_replay_summary_limite(session, state):
    for i in range(10):
        session.record(state, action="draw", description=f"carta {i}")
    lines = replay_summary(session, max_entries=3)
    # Deve ter 3 ações + 2 cabeçalho + 1 linha de aviso = ~6
    action_lines = [l for l in lines if "draw" in l]
    assert len(action_lines) <= 3


def test_snapshot_restaura_estado_completo(session, state, tmp_path):
    """Save -> sair -> load deve restaurar mãos, vida, turno e chain."""
    state.players["A"].hand = ["Snatch (red)", "Sizzle (red)"]
    state.players["B"].hand = ["Unmovable (blue)"]
    state.players["B"].life = 15
    state.active_player = "B"
    state.turn = 4
    session.record(state, action="draw", description="Snatch (red)")
    session.record(state, action="attack", description="Snatch (red) (4{p})")

    path = tmp_path / "partida.json"
    save_session(session, path)

    loaded = load_session(path)
    assert len(loaded.entries) == 2

    snap = loaded.entries[-1].state_snapshot
    restored = GameState.from_dict(snap)
    assert restored.players["A"].hand == ["Snatch (red)", "Sizzle (red)"]
    assert restored.players["B"].hand == ["Unmovable (blue)"]
    assert restored.players["B"].life == 15
    assert restored.active_player == "B"
    assert restored.turn == 4


# ---------------------------------------------------------------------------
# Testes de recording completo (todas as ações mutantes)
# ---------------------------------------------------------------------------
def test_registra_todos_tipos_de_acao(session, state):
    """Todas as ações mutantes devem gerar entradas no log."""
    acoes = [
        ("draw", "Comprou Snatch (red)"),
        ("pitch", "Snatch (red) → +1{r}"),
        ("arsenal", "Snatch (red) → arsenal"),
        ("play", "Jogou Snatch (red)"),
        ("attack", "Snatch (red) (4{p})"),
        ("weapon", "Star Fall (1{p})"),
        ("boost", "+2{p}"),
        ("arcane", "+1{a}"),
        ("defend", "Defendeu com Snatch (red)"),
        ("equip", "Blade Beckoner Helm: +1 de bloqueio"),
        ("resolve", "3{p} + 0{a} → acertou"),
        ("next", "Turno 2 → Enigma (B)"),
        ("switch", "Ativo: Enigma (B)"),
    ]
    for action, desc in acoes:
        entry = session.record(state, action=action, description=desc)
        assert entry.action == action
    assert len(session.entries) == len(acoes)


def test_registra_com_result_e_suggestions(session, state):
    """Entradas podem ter result e suggestions simultaneamente."""
    entry = session.record(
        state,
        action="resolve",
        description="3{p} + 1{a} → acertou",
        result=["On-hit: conferir efeitos", "Embodiment criado"],
        suggestions=["Considere usar equipment"],
    )
    assert entry.result == ["On-hit: conferir efeitos", "Embodiment criado"]
    assert entry.suggestions == ["Considere usar equipment"]


def test_sequencia_de_acoes_preserva_ordem(session, state):
    """Ações registradas mantêm a ordem cronológica."""
    session.record(state, action="draw", description="turno 1 draw")
    state.turn = 2
    session.record(state, action="attack", description="turno 2 attack")
    state.turn = 3
    session.record(state, action="resolve", description="turno 3 resolve")

    assert session.entries[0].turn == 1
    assert session.entries[1].turn == 2
    assert session.entries[2].turn == 3
    assert session.entries[0].action == "draw"
    assert session.entries[1].action == "attack"
    assert session.entries[2].action == "resolve"


def test_snapshot_cada_entrada(state):
    """Cada entrada deve conter snapshot independente do estado."""
    log = SessionLog(hero_a="Briar", hero_b="Enigma", start_time="2026-01-01T00:00:00")

    state.players["A"].hand = ["Card1"]
    log.record(state, action="draw", description="draw 1")

    state.players["A"].hand = ["Card1", "Card2"]
    state.turn = 2
    log.record(state, action="draw", description="draw 2")

    snap1 = GameState.from_dict(log.entries[0].state_snapshot)
    snap2 = GameState.from_dict(log.entries[1].state_snapshot)

    assert snap1.players["A"].hand == ["Card1"]
    assert snap1.turn == 1
    assert snap2.players["A"].hand == ["Card1", "Card2"]
    assert snap2.turn == 2


def test_replay_summary_acoes_completas(session, state):
    """replay_summary mostra todas as ações com formatação correta."""
    session.record(state, action="draw", description="Comprou A")
    session.record(state, action="attack", description="Atacou B")
    session.record(state, action="resolve", description="Resolveu")

    lines = replay_summary(session)
    text = "\n".join(lines)
    assert "draw" in text
    assert "attack" in text
    assert "resolve" in text


def test_save_load_roundtrip_com_todas_acoes(session, state, tmp_path):
    """Save/load preserva todas as entradas e seus campos."""
    session.record(state, action="draw", description="draw")
    session.record(
        state,
        action="attack",
        description="attack",
        result=["dano"],
        suggestions=["sug"],
    )
    session.record(state, action="next", description="next turn")

    path = tmp_path / "completo.json"
    save_session(session, path)
    loaded = load_session(path)

    assert len(loaded.entries) == 3
    assert loaded.entries[0].action == "draw"
    assert loaded.entries[1].action == "attack"
    assert loaded.entries[1].result == ["dano"]
    assert loaded.entries[1].suggestions == ["sug"]
    assert loaded.entries[2].action == "next"
