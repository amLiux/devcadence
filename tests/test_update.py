import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from update import _next_human_log_id, check_updates, print_check


def _patch_managed_files(tmp_path, monkeypatch, rel_path):
    """Patch _managed_files to return a single temp file mapping."""
    abs_path = tmp_path / rel_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)

    def fake_managed_files():
        return [(rel_path, abs_path)]

    monkeypatch.setattr("update._managed_files", fake_managed_files)
    return abs_path


def test_check_updates_reports_up_to_date(tmp_path, monkeypatch):
    managed = _patch_managed_files(tmp_path, monkeypatch, "scripts/tickets.py")
    content = b"print('hello')"
    managed.write_bytes(content)

    def fake_fetch(url):
        return content

    monkeypatch.setattr("update._fetch", fake_fetch)
    monkeypatch.chdir(tmp_path)
    results = check_updates()

    assert results[str(managed)]["status"] == "up-to-date"


def test_check_updates_reports_update_available(tmp_path, monkeypatch):
    managed = _patch_managed_files(tmp_path, monkeypatch, "scripts/tickets.py")
    managed.write_bytes(b"local content")

    def fake_fetch(url):
        return b"remote content"

    monkeypatch.setattr("update._fetch", fake_fetch)
    monkeypatch.chdir(tmp_path)
    results = check_updates()

    assert results[str(managed)]["status"] == "update-available"


def test_check_updates_reports_missing_remote(tmp_path, monkeypatch):
    managed = _patch_managed_files(tmp_path, monkeypatch, "scripts/tickets.py")
    managed.write_bytes(b"local")

    def fake_fetch(url):
        return None

    monkeypatch.setattr("update._fetch", fake_fetch)
    monkeypatch.chdir(tmp_path)
    results = check_updates()

    assert results[str(managed)]["status"] == "unavailable"


def test_next_human_log_id():
    log = [{"id": "hl-001"}, {"id": "hl-005"}]
    assert _next_human_log_id(log) == "hl-006"


def test_next_human_log_id_empty():
    assert _next_human_log_id([]) == "hl-001"
