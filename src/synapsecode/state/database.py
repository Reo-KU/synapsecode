"""SQLite state management with WAL mode."""

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


_SCHEMA = """\
CREATE TABLE IF NOT EXISTS sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    request     TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'running',
    created_at  REAL NOT NULL,
    finished_at REAL
);

CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER NOT NULL REFERENCES sessions(id),
    phase       TEXT NOT NULL,
    agent       TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending',
    started_at  REAL,
    finished_at REAL,
    result_text TEXT
);

CREATE TABLE IF NOT EXISTS agent_calls (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     INTEGER NOT NULL REFERENCES tasks(id),
    agent       TEXT NOT NULL,
    role        TEXT NOT NULL,
    prompt      TEXT,
    response    TEXT,
    cost_usd    REAL DEFAULT 0.0,
    duration_s  REAL DEFAULT 0.0,
    model       TEXT,
    created_at  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS cost_ledger (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER NOT NULL REFERENCES sessions(id),
    agent       TEXT NOT NULL,
    role        TEXT NOT NULL,
    cost_usd    REAL NOT NULL,
    model       TEXT,
    created_at  REAL NOT NULL
);
"""


class StateDB:
    """Thin wrapper around SQLite for persisting orchestration state."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        if db_path is None:
            db_dir = Path.home() / ".config" / "synapsecode"
            db_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(db_dir / "state.db")
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # -- Sessions --

    def create_session(self, request: str) -> int:
        cur = self._conn.execute(
            "INSERT INTO sessions (request, created_at) VALUES (?, ?)",
            (request, time.time()),
        )
        self._conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def finish_session(self, session_id: int, status: str = "completed") -> None:
        self._conn.execute(
            "UPDATE sessions SET status=?, finished_at=? WHERE id=?",
            (status, time.time(), session_id),
        )
        self._conn.commit()

    def get_session(self, session_id: int) -> Optional[Dict[str, Any]]:
        row = self._conn.execute(
            "SELECT * FROM sessions WHERE id=?", (session_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_sessions(self, limit: int = 20) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM sessions ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    # -- Tasks --

    def create_task(self, session_id: int, phase: str, agent: str) -> int:
        cur = self._conn.execute(
            "INSERT INTO tasks (session_id, phase, agent, started_at) VALUES (?, ?, ?, ?)",
            (session_id, phase, agent, time.time()),
        )
        self._conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def finish_task(self, task_id: int, status: str, result_text: str = "") -> None:
        self._conn.execute(
            "UPDATE tasks SET status=?, finished_at=?, result_text=? WHERE id=?",
            (status, time.time(), result_text, task_id),
        )
        self._conn.commit()

    # -- Agent calls --

    def record_agent_call(
        self,
        task_id: int,
        agent: str,
        role: str,
        prompt: str,
        response: str,
        cost_usd: float,
        duration_s: float,
        model: str,
    ) -> int:
        cur = self._conn.execute(
            "INSERT INTO agent_calls "
            "(task_id, agent, role, prompt, response, cost_usd, duration_s, model, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (task_id, agent, role, prompt, response, cost_usd, duration_s, model, time.time()),
        )
        self._conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    # -- Cost ledger --

    def record_cost(
        self, session_id: int, agent: str, role: str, cost_usd: float, model: str = ""
    ) -> None:
        self._conn.execute(
            "INSERT INTO cost_ledger (session_id, agent, role, cost_usd, model, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, agent, role, cost_usd, model, time.time()),
        )
        self._conn.commit()

    def session_total_cost(self, session_id: int) -> float:
        row = self._conn.execute(
            "SELECT COALESCE(SUM(cost_usd), 0.0) as total FROM cost_ledger WHERE session_id=?",
            (session_id,),
        ).fetchone()
        return float(row["total"]) if row else 0.0
