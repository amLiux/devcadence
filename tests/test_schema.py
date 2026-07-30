import json
from pathlib import Path

REQUIRED_LOG_FIELDS = {"id", "mode", "timestamp", "phase", "ticketIds", "global", "human", "machine"}
REQUIRED_PROGRESS_FIELDS = {"project", "currentPhase", "currentTicketIds", "lastMode", "cavemanMode", "workflow", "tickets", "humanLog"}
VALID_MODES = {"standup", "pair", "review", "checkout", "huddle"}


def test_log_schema():
    """Validate a sample log against schema"""
    sample = {
        "id": "2026-05-07-standup",
        "mode": "standup",
        "timestamp": "2026-05-07T00:00:00Z",
        "phase": 1,
        "ticketIds": ["DEV-01"],
        "global": False,
        "human": {"summary": "test", "notes": "test"},
        "machine": {"context": "test", "nextAction": "test"},
        "observations": [],
        "references": [],
    }
    assert REQUIRED_LOG_FIELDS.issubset(sample.keys())
    assert sample["mode"] in VALID_MODES
    assert isinstance(sample["ticketIds"], list)
    assert isinstance(sample["global"], bool)


def test_log_schema_with_metadata():
    """Validate a sample log with optional metadata"""
    sample = {
        "id": "2026-07-30-pair",
        "mode": "pair",
        "timestamp": "2026-07-30T00:00:00Z",
        "phase": 2,
        "ticketIds": ["DC-15"],
        "global": False,
        "human": {"summary": "test", "notes": "test"},
        "machine": {"context": "test", "nextAction": "test"},
        "observations": [],
        "references": [],
        "metadata": {
            "model": "kimi-k2.7-code",
            "model_provider": "opencode-go",
            "usage": {
                "prompt_tokens": 1234,
                "completion_tokens": 567,
                "total_tokens": 1801,
            },
        },
    }
    assert REQUIRED_LOG_FIELDS.issubset(sample.keys())
    assert sample["mode"] in VALID_MODES
    assert isinstance(sample["metadata"]["usage"]["total_tokens"], int)


def test_progress_schema():
    """Validate progress.json keys"""
    sample = {
        "project": "test",
        "currentPhase": 1,
        "currentTicketIds": [],
        "lastMode": "checkout",
        "cavemanMode": "full",
        "workflow": {"diagram": "", "skippable": [], "defaultStart": "standup"},
        "tickets": [],
        "humanLog": [],
        "observations": [],
    }
    assert REQUIRED_PROGRESS_FIELDS.issubset(sample.keys())
    assert sample["cavemanMode"] in ("lite", "full", "ultra")
