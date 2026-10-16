import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from storage import (
    aggregate_usage,
    db_path_for_progress,
    ensure_synced,
    get_logs,
    get_progress_summary,
    get_recent_human_log,
    get_tickets,
)


@pytest.fixture
def sample_progress(tmp_path):
    progress = {
        "project": "test",
        "currentPhase": 2,
        "currentTicketIds": ["T-01"],
        "lastMode": "checkout",
        "cavemanMode": "full",
        "workflow": {"diagram": "", "skippable": [], "defaultStart": "standup"},
        "tickets": [
            {
                "id": "T-01",
                "phase": 2,
                "task": "First ticket",
                "files": ["a.py"],
                "acceptance": ["AC1"],
                "priority": "high",
                "status": "in-progress",
                "createdAt": "2026-10-01T00:00:00Z",
                "completedAt": None,
                "reviewStatus": None,
            },
            {
                "id": "T-02",
                "phase": 2,
                "task": "Second ticket",
                "files": [],
                "acceptance": [],
                "priority": "low",
                "status": "pending",
                "createdAt": "2026-10-02T00:00:00Z",
                "completedAt": None,
                "reviewStatus": None,
            },
        ],
        "humanLog": [
            {
                "id": "hl-001",
                "type": "milestone",
                "logRef": "2026-10-01-standup",
                "message": "Started",
                "timestamp": "2026-10-01T10:00:00Z",
                "phase": 2,
                "ticketIds": ["T-01"],
                "author": "user",
                "tags": ["standup"],
            }
        ],
        "observations": [
            {
                "id": "obs-001",
                "pattern": "Test pattern",
                "severity": "suggestion",
                "confidence": "emerging",
                "ticketIds": ["T-01"],
                "suggestion": "Do better",
                "firstSeen": "2026-10-01T00:00:00Z",
                "timesObserved": 1,
            }
        ],
    }
    path = tmp_path / "progress.json"
    path.write_text(json.dumps(progress))
    return path


@pytest.fixture
def sample_logs(tmp_path, sample_progress):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log = {
        "id": "2026-10-01-standup",
        "mode": "standup",
        "timestamp": "2026-10-01T12:00:00Z",
        "phase": 2,
        "ticketIds": ["T-01"],
        "global": False,
        "human": {"summary": "Standup", "notes": "Notes"},
        "machine": {"context": "Context", "nextAction": "Next"},
        "observations": [],
        "references": [],
        "metadata": {
            "model": "kimi-k2.7-code",
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
            },
        },
    }
    (log_dir / "2026-10-01-standup.json").write_text(json.dumps(log))
    return log_dir


def test_db_path_for_progress(sample_progress):
    assert db_path_for_progress(sample_progress) == sample_progress.parent / ".devcadence.db"


def test_ensure_synced_creates_db(sample_progress, sample_logs):
    conn = ensure_synced(sample_progress, sample_logs)
    assert (sample_progress.parent / ".devcadence.db").exists()
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "tickets" in tables
    assert "logs" in tables
    assert "human_log" in tables
    assert "observations" in tables


def test_get_tickets(sample_progress, sample_logs):
    conn = ensure_synced(sample_progress, sample_logs)
    all_tickets = get_tickets(conn)
    assert len(all_tickets) == 2
    high = get_tickets(conn, priority="high")
    assert len(high) == 1
    assert high[0]["id"] == "T-01"


def test_get_logs(sample_progress, sample_logs):
    conn = ensure_synced(sample_progress, sample_logs)
    logs = get_logs(conn)
    assert len(logs) == 1
    assert logs[0]["mode"] == "standup"

    by_ticket = get_logs(conn, ticket_id="T-01")
    assert len(by_ticket) == 1

    by_mode = get_logs(conn, mode="pair")
    assert len(by_mode) == 0


def test_get_progress_summary(sample_progress, sample_logs):
    conn = ensure_synced(sample_progress, sample_logs)
    summary = get_progress_summary(conn)
    assert summary == {"total": 2, "pending": 1, "in_progress": 1, "completed": 0}


def test_get_recent_human_log(sample_progress, sample_logs):
    conn = ensure_synced(sample_progress, sample_logs)
    recent = get_recent_human_log(conn, limit=5)
    assert len(recent) == 1
    assert recent[0]["id"] == "hl-001"


def test_aggregate_usage(sample_progress, sample_logs):
    conn = ensure_synced(sample_progress, sample_logs)
    totals, per_ticket = aggregate_usage(conn)
    assert totals["total"] == 150
    assert per_ticket["T-01"]["total"] == 150


def test_incremental_sync(sample_progress, sample_logs):
    conn = ensure_synced(sample_progress, sample_logs)
    # Re-sync without changes should be cheap and keep data
    conn2 = ensure_synced(sample_progress, sample_logs)
    assert len(get_tickets(conn2)) == 2

    # Modify progress.json
    data = json.loads(sample_progress.read_text())
    data["tickets"].append(
        {
            "id": "T-03",
            "phase": 2,
            "task": "Third ticket",
            "files": [],
            "acceptance": [],
            "priority": "medium",
            "status": "pending",
            "createdAt": "2026-10-03T00:00:00Z",
            "completedAt": None,
            "reviewStatus": None,
        }
    )
    sample_progress.write_text(json.dumps(data))
    conn3 = ensure_synced(sample_progress, sample_logs)
    assert len(get_tickets(conn3)) == 3
