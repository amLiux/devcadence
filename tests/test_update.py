import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from update import _next_human_log_id, check_updates, print_check


def test_check_updates_reports_up_to_date(tmp_path, monkeypatch):
    # Simulate a project with a managed file that matches upstream
    managed = tmp_path / "scripts" / "tickets.py"
    managed.parent.mkdir(parents=True)
    content = b"print('hello')"
    managed.write_bytes(content)

    # Patch remote fetch to return same content
    def fake_fetch(url):
        return content

    monkeypatch.setattr("update._fetch", fake_fetch)

    # Patch MANAGED_FILES to only include our temp file
    monkeypatch.setattr("update.MANAGED_FILES", [str(managed.relative_to(tmp_path))])

    import update

    update.MANAGED_FILES = [str(managed.relative_to(tmp_path))]
    monkeypatch.chdir(tmp_path)
    results = check_updates()

    rel = str(managed.relative_to(tmp_path))
    assert results[rel]["status"] == "up-to-date"


def test_check_updates_reports_update_available(tmp_path, monkeypatch):
    managed = tmp_path / "scripts" / "tickets.py"
    managed.parent.mkdir(parents=True)
    managed.write_bytes(b"local content")

    def fake_fetch(url):
        return b"remote content"

    monkeypatch.setattr("update._fetch", fake_fetch)

    import update

    update.MANAGED_FILES = [str(managed.relative_to(tmp_path))]
    monkeypatch.chdir(tmp_path)
    results = check_updates()

    rel = str(managed.relative_to(tmp_path))
    assert results[rel]["status"] == "update-available"


def test_check_updates_reports_missing_remote(tmp_path, monkeypatch):
    managed = tmp_path / "scripts" / "tickets.py"
    managed.parent.mkdir(parents=True)
    managed.write_bytes(b"local")

    def fake_fetch(url):
        return None

    monkeypatch.setattr("update._fetch", fake_fetch)

    import update

    update.MANAGED_FILES = [str(managed.relative_to(tmp_path))]
    monkeypatch.chdir(tmp_path)
    results = check_updates()

    rel = str(managed.relative_to(tmp_path))
    assert results[rel]["status"] == "unavailable"


def test_next_human_log_id():
    log = [{"id": "hl-001"}, {"id": "hl-005"}]
    assert _next_human_log_id(log) == "hl-006"


def test_next_human_log_id_empty():
    assert _next_human_log_id([]) == "hl-001"
