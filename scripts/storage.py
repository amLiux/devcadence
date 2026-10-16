#!/usr/bin/env python3
"""DevCadence SQLite storage backend.

Hybrid design: JSON files remain canonical. This module builds and maintains a
local SQLite index (``.devcadence.db`` next to ``progress.json``) for fast
queries. The index is rebuilt lazily by comparing file hashes stored in the DB.
"""

import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path


def _hash_file(path: Path) -> str:
    """Return SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _json_blob(value) -> str:
    return json.dumps(value, default=str)


def _load_json(path: Path):
    with open(path) as f:
        return json.load(f)


PROGRESS_PATH_ENV = os.environ.get("PROGRESS_JSON", "")
DEFAULT_PROGRESS_LOCATIONS = [
    Path.home() / "docs" / "devcadence" / "progress.json",
    Path("progress.json"),
]


def find_progress() -> Path | None:
    if PROGRESS_PATH_ENV and Path(PROGRESS_PATH_ENV).exists():
        return Path(PROGRESS_PATH_ENV)
    for p in DEFAULT_PROGRESS_LOCATIONS:
        if p.exists():
            return p
    return None


def db_path_for_progress(progress_path: Path) -> Path:
    return progress_path.parent / ".devcadence.db"


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tickets (
            id TEXT PRIMARY KEY,
            phase INTEGER,
            task TEXT,
            files TEXT,            -- JSON array
            acceptance TEXT,       -- JSON array
            priority TEXT,
            status TEXT,
            created_at TEXT,
            completed_at TEXT,
            review_status TEXT,
            raw TEXT               -- full JSON blob
        );

        CREATE TABLE IF NOT EXISTS human_log (
            id TEXT PRIMARY KEY,
            type TEXT,
            log_ref TEXT,
            message TEXT,
            timestamp TEXT,
            phase INTEGER,
            author TEXT,
            tags TEXT,             -- JSON array
            raw TEXT               -- full JSON blob
        );

        CREATE TABLE IF NOT EXISTS human_log_tickets (
            human_log_id TEXT NOT NULL,
            ticket_id TEXT NOT NULL,
            PRIMARY KEY (human_log_id, ticket_id)
        );

        CREATE TABLE IF NOT EXISTS observations (
            id TEXT PRIMARY KEY,
            pattern TEXT,
            severity TEXT,
            confidence TEXT,
            suggestion TEXT,
            first_seen TEXT,
            times_observed INTEGER,
            raw TEXT               -- full JSON blob
        );

        CREATE TABLE IF NOT EXISTS observation_tickets (
            observation_id TEXT NOT NULL,
            ticket_id TEXT NOT NULL,
            PRIMARY KEY (observation_id, ticket_id)
        );

        CREATE TABLE IF NOT EXISTS logs (
            id TEXT PRIMARY KEY,
            file_name TEXT,
            mode TEXT,
            timestamp TEXT,
            phase INTEGER,
            global INTEGER,
            summary TEXT,
            notes TEXT,
            context TEXT,
            next_action TEXT,
            model TEXT,
            prompt_tokens INTEGER,
            completion_tokens INTEGER,
            total_tokens INTEGER,
            raw TEXT               -- full JSON blob
        );

        CREATE TABLE IF NOT EXISTS log_tickets (
            log_id TEXT NOT NULL,
            ticket_id TEXT NOT NULL,
            PRIMARY KEY (log_id, ticket_id)
        );

        CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
        CREATE INDEX IF NOT EXISTS idx_tickets_priority ON tickets(priority);
        CREATE INDEX IF NOT EXISTS idx_tickets_phase ON tickets(phase);

        CREATE INDEX IF NOT EXISTS idx_logs_mode ON logs(mode);
        CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp);
        CREATE INDEX IF NOT EXISTS idx_logs_global ON logs(global);
        CREATE INDEX IF NOT EXISTS idx_logs_model ON logs(model);
        CREATE INDEX IF NOT EXISTS idx_log_tickets_ticket ON log_tickets(ticket_id);
        CREATE INDEX IF NOT EXISTS idx_human_log_tickets_ticket ON human_log_tickets(ticket_id);
        """
    )
    conn.commit()


def _sync_progress(conn: sqlite3.Connection, progress_path: Path) -> None:
    current_hash = _hash_file(progress_path)
    stored_hash = conn.execute(
        "SELECT value FROM meta WHERE key = 'progress_hash'"
    ).fetchone()

    if stored_hash and stored_hash[0] == current_hash:
        return

    data = _load_json(progress_path)

    # Tickets
    conn.execute("DELETE FROM tickets")
    for t in data.get("tickets", []):
        conn.execute(
            """
            INSERT INTO tickets (id, phase, task, files, acceptance, priority, status,
                                 created_at, completed_at, review_status, raw)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                t.get("id"),
                t.get("phase"),
                t.get("task"),
                _json_blob(t.get("files", [])),
                _json_blob(t.get("acceptance", [])),
                t.get("priority", "medium"),
                t.get("status"),
                t.get("createdAt"),
                t.get("completedAt"),
                t.get("reviewStatus"),
                _json_blob(t),
            ),
        )

    # Human log
    conn.execute("DELETE FROM human_log")
    conn.execute("DELETE FROM human_log_tickets")
    for hl in data.get("humanLog", []):
        conn.execute(
            """
            INSERT INTO human_log (id, type, log_ref, message, timestamp, phase, author, tags, raw)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                hl.get("id"),
                hl.get("type"),
                hl.get("logRef"),
                hl.get("message"),
                hl.get("timestamp"),
                hl.get("phase"),
                hl.get("author"),
                _json_blob(hl.get("tags", [])),
                _json_blob(hl),
            ),
        )
        for tid in hl.get("ticketIds", []):
            conn.execute(
                "INSERT OR IGNORE INTO human_log_tickets (human_log_id, ticket_id) VALUES (?, ?)",
                (hl.get("id"), tid),
            )

    # Observations
    conn.execute("DELETE FROM observations")
    conn.execute("DELETE FROM observation_tickets")
    for obs in data.get("observations", []):
        conn.execute(
            """
            INSERT INTO observations (id, pattern, severity, confidence, suggestion,
                                      first_seen, times_observed, raw)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                obs.get("id"),
                obs.get("pattern"),
                obs.get("severity"),
                obs.get("confidence"),
                obs.get("suggestion"),
                obs.get("firstSeen"),
                obs.get("timesObserved", 0),
                _json_blob(obs),
            ),
        )
        for tid in obs.get("ticketIds", []):
            conn.execute(
                "INSERT OR IGNORE INTO observation_tickets (observation_id, ticket_id) VALUES (?, ?)",
                (obs.get("id"), tid),
            )

    conn.execute(
        "INSERT OR REPLACE INTO meta (key, value) VALUES ('progress_hash', ?)",
        (current_hash,),
    )
    conn.commit()


def _sync_logs(conn: sqlite3.Connection, log_dir: Path) -> None:
    if not log_dir.is_dir():
        return

    known_files = {
        row[0] for row in conn.execute("SELECT file_name FROM logs").fetchall()
    }
    current_files = {f.name for f in log_dir.glob("*.json")}

    # Remove entries for deleted logs
    for removed in known_files - current_files:
        conn.execute("DELETE FROM log_tickets WHERE log_id IN (SELECT id FROM logs WHERE file_name = ?)", (removed,))
        conn.execute("DELETE FROM logs WHERE file_name = ?", (removed,))

    for f in sorted(log_dir.glob("*.json")):
        current_hash = _hash_file(f)
        stored = conn.execute(
            "SELECT value FROM meta WHERE key = ?",
            (f"log_hash:{f.name}",),
        ).fetchone()

        if stored and stored[0] == current_hash:
            continue

        try:
            log = _load_json(f)
        except (json.JSONDecodeError, IOError):
            continue

        log_id = log.get("id", f.name)
        meta = log.get("metadata", {}) or {}
        usage = meta.get("usage") or {}

        # Remove stale data for this log if re-syncing
        conn.execute("DELETE FROM log_tickets WHERE log_id = ?", (log_id,))
        conn.execute("DELETE FROM logs WHERE id = ?", (log_id,))

        conn.execute(
            """
            INSERT INTO logs (id, file_name, mode, timestamp, phase, global, summary, notes,
                              context, next_action, model, prompt_tokens, completion_tokens,
                              total_tokens, raw)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                log_id,
                f.name,
                log.get("mode"),
                log.get("timestamp"),
                log.get("phase"),
                1 if log.get("global") else 0,
                log.get("human", {}).get("summary"),
                log.get("human", {}).get("notes"),
                log.get("machine", {}).get("context"),
                log.get("machine", {}).get("nextAction"),
                meta.get("model"),
                usage.get("prompt_tokens"),
                usage.get("completion_tokens"),
                usage.get("total_tokens"),
                _json_blob(log),
            ),
        )

        for tid in log.get("ticketIds", []):
            conn.execute(
                "INSERT OR IGNORE INTO log_tickets (log_id, ticket_id) VALUES (?, ?)",
                (log_id, tid),
            )

        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            (f"log_hash:{f.name}", current_hash),
        )

    conn.commit()


def ensure_synced(progress_path: Path, log_dir: Path | None = None) -> sqlite3.Connection:
    """Open the SQLite index, initialize schema, and sync with JSON files."""
    db = db_path_for_progress(progress_path)
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    _sync_progress(conn, progress_path)
    if log_dir is None:
        log_dir = progress_path.parent / "logs"
    _sync_logs(conn, log_dir)
    return conn


# -----------------------------------------------------------------------------
# Query helpers
# -----------------------------------------------------------------------------


def get_tickets(
    conn: sqlite3.Connection,
    status: str | None = None,
    priority: str | None = None,
    phase: int | None = None,
) -> list[dict]:
    query = "SELECT raw FROM tickets WHERE 1=1"
    params = []
    if status:
        query += " AND status = ?"
        params.append(status)
    if priority:
        query += " AND priority = ?"
        params.append(priority)
    if phase is not None:
        query += " AND phase = ?"
        params.append(phase)
    return [json.loads(row[0]) for row in conn.execute(query, params).fetchall()]


def get_logs(
    conn: sqlite3.Connection,
    mode: str | None = None,
    ticket_id: str | None = None,
    days: int | None = None,
    global_only: bool = False,
    model: str | None = None,
) -> list[dict]:
    if ticket_id:
        query = """
            SELECT l.raw FROM logs l
            JOIN log_tickets lt ON l.id = lt.log_id
            WHERE lt.ticket_id = ?
        """
        params = [ticket_id]
    else:
        query = "SELECT raw FROM logs l WHERE 1=1"
        params = []

    if mode:
        query += " AND l.mode = ?"
        params.append(mode)
    if global_only:
        query += " AND l.global = 1"
    if model:
        query += " AND l.model = ?"
        params.append(model)
    if days is not None:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        query += " AND l.timestamp >= ?"
        params.append(cutoff)

    query += " ORDER BY l.timestamp"
    return [json.loads(row[0]) for row in conn.execute(query, params).fetchall()]


def get_progress_summary(conn: sqlite3.Connection) -> dict:
    # Top-level config is still read from JSON once; this helper answers counts.
    total = conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
    pending = conn.execute(
        "SELECT COUNT(*) FROM tickets WHERE status = 'pending'"
    ).fetchone()[0]
    in_progress = conn.execute(
        "SELECT COUNT(*) FROM tickets WHERE status = 'in-progress'"
    ).fetchone()[0]
    completed = conn.execute(
        "SELECT COUNT(*) FROM tickets WHERE status = 'completed'"
    ).fetchone()[0]
    return {
        "total": total,
        "pending": pending,
        "in_progress": in_progress,
        "completed": completed,
    }


def get_recent_human_log(conn: sqlite3.Connection, limit: int = 3) -> list[dict]:
    rows = conn.execute(
        "SELECT raw FROM human_log ORDER BY timestamp DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [json.loads(row[0]) for row in rows]


def aggregate_usage(conn: sqlite3.Connection) -> tuple[dict, dict]:
    totals = {"prompt": 0, "completion": 0, "total": 0}
    per_ticket: dict[str, dict] = {}

    rows = conn.execute(
        """
        SELECT l.prompt_tokens, l.completion_tokens, l.total_tokens, lt.ticket_id
        FROM logs l
        LEFT JOIN log_tickets lt ON l.id = lt.log_id
        WHERE l.total_tokens IS NOT NULL
        """
    ).fetchall()

    for prompt, completion, total, ticket_id in rows:
        if total is None:
            continue
        totals["prompt"] += prompt or 0
        totals["completion"] += completion or 0
        totals["total"] += total or 0
        if ticket_id:
            if ticket_id not in per_ticket:
                per_ticket[ticket_id] = {"prompt": 0, "completion": 0, "total": 0}
            per_ticket[ticket_id]["prompt"] += prompt or 0
            per_ticket[ticket_id]["completion"] += completion or 0
            per_ticket[ticket_id]["total"] += total or 0

    return totals, per_ticket


def get_usage_for_log(log: dict) -> dict | None:
    """Extract usage from a raw log dict (used by callers that already have JSON)."""
    usage = log.get("metadata", {}).get("usage")
    if not usage:
        return None
    try:
        return {
            "prompt": int(usage.get("prompt_tokens", 0) or 0),
            "completion": int(usage.get("completion_tokens", 0) or 0),
            "total": int(usage.get("total_tokens", 0) or 0),
        }
    except (ValueError, TypeError):
        return None


def sync_only(progress_path: Path, log_dir: Path | None = None) -> None:
    """Build/update the SQLite index without returning a connection."""
    with ensure_synced(progress_path, log_dir) as conn:
        conn.execute("PRAGMA optimize")


def try_sync(
    progress_path: Path,
    log_dir: Path | None = None,
    no_sqlite: bool = False,
) -> sqlite3.Connection | None:
    """Return a synced SQLite connection, or None if SQLite is disabled or fails.

    Prints a warning to stderr when falling back to JSON.
    """
    if no_sqlite:
        return None
    try:
        return ensure_synced(progress_path, log_dir)
    except Exception as e:
        print(f"SQLite index failed ({e}); falling back to JSON.", file=sys.stderr)
        return None


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Build or update DevCadence SQLite index")
    parser.add_argument("--progress", help="Path to progress.json")
    parser.add_argument("--log-dir", help="Path to logs directory")
    args = parser.parse_args()

    if args.progress:
        progress_path = Path(args.progress)
    else:
        progress_path = find_progress()

    if not progress_path:
        print("progress.json not found. Set PROGRESS_JSON or use --progress.", file=sys.stderr)
        sys.exit(1)

    log_dir = Path(args.log_dir) if args.log_dir else None
    sync_only(progress_path, log_dir)
    db = db_path_for_progress(progress_path)
    print(f"SQLite index updated: {db}")


if __name__ == "__main__":
    main()
