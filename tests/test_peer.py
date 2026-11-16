import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import peer


class FakeApi:
    """Minimal stand-in for `opencode api`."""

    def __init__(self):
        self.calls = []
        self.sessions = {
            "/repo": [
                {"id": "ses_new", "title": "Hortus OIDC", "updated": 2},
                {"id": "ses_old", "title": "Hortus", "updated": 1},
            ]
        }
        self.known = {"ses_new", "ses_old"}
        self.cost = 1.0
        self.tokens = {"input": 100, "output": 10, "reasoning": 5}
        self.reply = "Listo: 22/22 en verde."
        self.fail_sessions = set()

    def __call__(self, method, path, params=None, data=None, timeout=None):
        self.calls.append((method, path, params, data))
        if method == "GET" and path == "/api/session":
            return {"data": self.sessions.get(params.get("directory"), [])}
        if method == "GET" and path.startswith("/api/session/") and path.count("/") == 3:
            session_id = path.rsplit("/", 1)[-1]
            if session_id not in self.known or session_id in self.fail_sessions:
                raise peer.PeerError(f"GET {path} failed: HTTP 404")
            return {
                "data": {
                    "id": session_id,
                    "cost": self.cost,
                    "tokens": dict(self.tokens),
                }
            }
        if method == "GET" and path.endswith("/message"):
            return {
                "data": [
                    {
                        "content": [
                            {"type": "reasoning", "text": "hidden"},
                            {"type": "text", "text": self.reply},
                        ]
                    }
                ]
            }
        if method == "POST" and path.endswith("/prompt"):
            return {"data": {"id": data["id"]}}
        if method == "POST" and path.endswith("/wait"):
            return None
        if method == "DELETE" and "/inbox/" in path:
            return None
        raise AssertionError(f"unexpected call {method} {path}")


@pytest.fixture
def fake():
    return FakeApi()


@pytest.fixture
def peer_setup(tmp_path, fake):
    registry = tmp_path / "config" / "peers.json"
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Hortus\nAuth service\n")
    log_dir = tmp_path / "logs"
    sme_path = tmp_path / "config" / "peers" / "backend.md"
    fake.sessions[str(repo.resolve())] = [
        {"id": "ses_new", "title": "Hortus OIDC", "updated": 2},
        {"id": "ses_old", "title": "Hortus", "updated": 1},
    ]
    entry = peer.add_peer(
        "backend",
        str(repo),
        log_dir=str(tmp_path / "docs" / "repo"),
        turns=4,
        registry=registry,
        sme_path=sme_path,
        require_git=False,
        api=fake,
    )
    # point the fake at the real directory key
    return {
        "registry": registry,
        "repo": repo,
        "log_dir": log_dir,
        "sme_path": sme_path,
        "entry": entry,
        "fake": fake,
    }


def test_add_peer_writes_registry_and_sme_without_touching_repo(peer_setup):
    entry = peer_setup["entry"]
    assert entry["alias"] == "backend"
    assert entry["sessionId"] == "ses_new"
    assert peer_setup["registry"].exists()
    assert peer_setup["sme_path"].exists()
    assert "# Peer SME: backend" in peer_setup["sme_path"].read_text()

    registry = json.loads(peer_setup["registry"].read_text())
    assert registry["peers"]["backend"]["directory"] == str(peer_setup["repo"].resolve())

    # read-only promise: only README existed in the repo before and after
    assert [p.name for p in peer_setup["repo"].iterdir()] == ["README.md"]


def test_add_peer_rejects_bad_alias_and_duplicates(peer_setup, tmp_path):
    with pytest.raises(peer.PeerError):
        peer.add_peer("Backend!", str(peer_setup["repo"]), registry=peer_setup["registry"],
                      require_git=False, api=peer_setup["fake"])
    with pytest.raises(peer.PeerError):
        peer.add_peer("backend", str(peer_setup["repo"]), registry=peer_setup["registry"],
                      require_git=False, api=peer_setup["fake"])


def test_context_block_reads_peer_progress_only(tmp_path, peer_setup):
    log_dir = Path(peer_setup["entry"]["logDir"])
    log_dir.mkdir(parents=True)
    (log_dir / "progress.json").write_text(json.dumps({
        "lastMode": "pair",
        "currentTicketIds": ["DC-31"],
        "tickets": [
            {"id": "DC-31", "status": "in-progress", "priority": "high"},
            {"id": "DC-17", "status": "pending", "priority": "high"},
            {"id": "DC-04", "status": "pending", "priority": "low"},
        ],
        "humanLog": [{"message": "rediseñando migración"}],
    }))

    block = peer.context_block(peer_setup["entry"])

    assert "in-progress DC-31" in block
    assert "pending high DC-17" in block
    assert "rediseñando migración" in block
    assert "mode pair" in block


def test_context_block_degrades_on_bad_json(peer_setup):
    log_dir = Path(peer_setup["entry"]["logDir"])
    log_dir.mkdir(parents=True)
    (log_dir / "progress.json").write_text("{not json")
    assert peer.context_block(peer_setup["entry"]) == ""


def test_envelope_has_provenance_and_boundaries():
    text = peer.envelope(
        "backend", "estimate the endpoint", project="devcadence",
        ticket="DC-43", turn=2, budget=4, thread="t", context="in-progress DC-31",
    )
    assert "alias=backend" in text
    assert "ticket=DC-43" in text
    assert "turn=2/4" in text
    assert "context: in-progress DC-31" in text
    assert "request: estimate the endpoint" in text
    assert "no edites tu repo" in text


def test_send_queue_payload_and_jsonl(peer_setup, fake):
    record = peer.send_peer(
        "backend", "estimate the endpoint",
        ticket="DC-43", thread="t1", wait=True,
        registry=peer_setup["registry"], log_dir=peer_setup["log_dir"], api=fake,
    )
    assert record["delivery"] == "queue"
    assert record["turn"] == 1
    assert record["response"].startswith("Listo")
    assert record["messageId"].startswith("msg_")

    prompt = next(c for c in fake.calls if c[1].endswith("/prompt"))
    payload = prompt[3]
    assert payload["delivery"] == "queue"
    assert payload["metadata"]["devcadence"]["ticket"] == "DC-43"
    assert payload["metadata"]["devcadence"]["turn"] == 1
    assert payload["id"].startswith("msg_")
    assert "boundaries:" in payload["text"]

    lines = (peer_setup["log_dir"] / "peers" / "exchanges.jsonl").read_text().splitlines()
    assert json.loads(lines[0])["type"] == "send"


def test_send_steer_flag(peer_setup, fake):
    peer.send_peer(
        "backend", "urgent", delivery="steer", thread="t2",
        registry=peer_setup["registry"], log_dir=peer_setup["log_dir"], api=fake,
    )
    prompt = next(c for c in fake.calls if c[1].endswith("/prompt"))
    assert prompt[3]["delivery"] == "steer"


def test_turn_budget_stops_after_four(peer_setup, fake):
    for index in range(4):
        peer.send_peer(
            "backend", f"turn {index}", thread="budget",
            registry=peer_setup["registry"], log_dir=peer_setup["log_dir"], api=fake,
        )
    with pytest.raises(peer.PeerError, match="budget exhausted"):
        peer.send_peer(
            "backend", "one too many", thread="budget",
            registry=peer_setup["registry"], log_dir=peer_setup["log_dir"], api=fake,
        )
    # explicit continuation works
    record = peer.send_peer(
        "backend", "continue", thread="budget", new_thread=True,
        registry=peer_setup["registry"], log_dir=peer_setup["log_dir"], api=fake,
    )
    assert record["turn"] == 1


def test_secret_scan_blocks_and_override_allows(peer_setup, fake):
    with pytest.raises(peer.PeerError, match="secrets"):
        peer.send_peer(
            "backend", "use sk-abcdefghijklmnopqrstuvwx",
            registry=peer_setup["registry"], log_dir=peer_setup["log_dir"], api=fake,
        )
    record = peer.send_peer(
        "backend", "use sk-abcdefghijklmnopqrstuvwx", allow_secrets=True,
        registry=peer_setup["registry"], log_dir=peer_setup["log_dir"], api=fake,
    )
    assert record["messageId"].startswith("msg_")


def test_read_extracts_text_and_can_wait(peer_setup, fake):
    record = peer.read_peer(
        "backend", wait=True, registry=peer_setup["registry"],
        log_dir=peer_setup["log_dir"], api=fake,
    )
    assert record["response"] == "Listo: 22/22 en verde."
    assert any(c[1].endswith("/wait") for c in fake.calls)
    assert "hidden" not in record["response"]


def test_retract_calls_inbox_delete(peer_setup, fake):
    peer.retract_peer(
        "backend", "msg_abc", registry=peer_setup["registry"], api=fake
    )
    delete = next(c for c in fake.calls if c[0] == "DELETE")
    assert delete[1] == "/api/session/ses_new/inbox/msg_abc"


def test_stale_pin_falls_back_to_newest_session(peer_setup, fake):
    entry = dict(peer_setup["entry"])
    entry["sessionId"] = "ses_deleted"
    fake.fail_sessions.add("ses_deleted")
    assert peer.resolve_session(entry, api=fake) == "ses_new"


def test_metrics_delta_reports_cost_and_tokens():
    before = {"cost": 1.0, "tokens": {"input": 100, "output": 10}}
    after = {"cost": 1.25, "tokens": {"input": 160, "output": 30}}
    assert peer._metrics_delta(before, after) == {
        "cost": 0.25,
        "tokens": {"input": 60, "output": 20},
    }
