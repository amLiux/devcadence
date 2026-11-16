#!/usr/bin/env python3
"""DevCadence peer utility.

Message another opencode agent session through the local opencode HTTP API.
Read-only with respect to the peer: this module never writes to the peer's
repo, progress.json, logs or SQLite index.

Design: ~/docs/<project>/peers/design-v1.md (DC-43).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_TURNS = 4
DEFAULT_WAIT_TIMEOUT = 600
ALIAS_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,30}$")

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"eyJ[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
]

SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", ".venv", "venv", "dist", "build",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "target",
}


class PeerError(Exception):
    """Raised when a peer operation cannot be completed."""


# --------------------------------------------------------------------------- #
# paths / config
# --------------------------------------------------------------------------- #

def config_home() -> Path:
    override = os.environ.get("DEVCADENCE_PEER_HOME", "")
    if override:
        return Path(override).expanduser()
    base = os.environ.get("XDG_CONFIG_HOME", "")
    root = Path(base).expanduser() if base else Path.home() / ".config"
    return root / "devcadence"


def registry_path() -> Path:
    return config_home() / "peers.json"


def sme_dir() -> Path:
    return config_home() / "peers"


def default_log_dir() -> Path:
    override = os.environ.get("DEVCADENCE_LOG_DIR", "")
    if override:
        return Path(override).expanduser()
    try:
        from storage import find_progress  # same directory when installed

        progress = find_progress()
        if progress:
            return progress.parent
    except Exception:  # pragma: no cover - storage always ships alongside
        pass
    return Path.home() / "docs" / "devcadence"


def exchanges_path(log_dir: Optional[Path] = None) -> Path:
    return (log_dir or default_log_dir()) / "peers" / "exchanges.jsonl"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text)
    tmp.replace(path)


def load_registry(path: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    path = path or registry_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        raise PeerError(f"registry is not valid JSON: {path} ({exc})")
    peers = data.get("peers", data if isinstance(data, dict) else {})
    if not isinstance(peers, dict):
        raise PeerError(f"registry has no 'peers' object: {path}")
    return peers


def save_registry(peers: Dict[str, Dict[str, Any]], path: Optional[Path] = None) -> None:
    path = path or registry_path()
    _atomic_write(path, json.dumps({"peers": peers}, indent=2, ensure_ascii=False) + "\n")


def get_peer(alias: str, path: Optional[Path] = None) -> Dict[str, Any]:
    peers = load_registry(path)
    if alias not in peers:
        known = ", ".join(sorted(peers)) or "none"
        raise PeerError(f"unknown peer '{alias}' (registered: {known})")
    return peers[alias]


def _expand(path: str) -> Path:
    return Path(path).expanduser().resolve()


# --------------------------------------------------------------------------- #
# opencode API
# --------------------------------------------------------------------------- #

def _run_api(
    method: str,
    path: str,
    params: Optional[Dict[str, Any]] = None,
    data: Optional[Dict[str, Any]] = None,
    timeout: Optional[int] = None,
) -> Any:
    """Call `opencode api` and return the decoded JSON body (or None)."""
    cmd = ["opencode", "api", method, path]
    for key, value in (params or {}).items():
        if value is not None:
            cmd += ["--param", f"{key}={value}"]
    if data is not None:
        cmd += ["--data", json.dumps(data)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        raise PeerError("opencode CLI not found in PATH")
    except subprocess.TimeoutExpired:
        raise PeerError(f"opencode api timed out after {timeout}s: {method} {path}")
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise PeerError(f"{method} {path} failed: {detail}")
    body = (result.stdout or "").strip()
    if not body:
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise PeerError(f"{method} {path} returned non-JSON output: {exc}")


def list_sessions(directory: Path, api=_run_api, limit: int = 10) -> List[Dict[str, Any]]:
    body = api("GET", "/api/session", {"directory": str(directory), "limit": limit, "order": "desc"})
    return (body or {}).get("data", []) or []


def get_session(session_id: str, api=_run_api) -> Dict[str, Any]:
    body = api("GET", f"/api/session/{session_id}")
    return (body or {}).get("data", {}) or {}


def resolve_session(peer: Dict[str, Any], api=_run_api) -> str:
    pinned = peer.get("sessionId")
    if pinned:
        try:
            get_session(pinned, api=api)
            return pinned
        except PeerError:
            pass  # stale pin: fall through to newest
    sessions = list_sessions(Path(peer["directory"]), api=api)
    if not sessions:
        raise PeerError(
            f"no opencode session found in {peer['directory']} — open opencode there once"
        )
    return sessions[0]["id"]


def _metrics(session_id: str, api=_run_api) -> Dict[str, Any]:
    data = get_session(session_id, api=api)
    return {"cost": data.get("cost"), "tokens": data.get("tokens")}


def _copy_metrics(value: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    return json.loads(json.dumps(value)) if value else value


def _metrics_delta(before: Optional[Dict[str, Any]], after: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not before or not after:
        return {}
    cost = None
    if isinstance(before.get("cost"), (int, float)) and isinstance(after.get("cost"), (int, float)):
        cost = round(after["cost"] - before["cost"], 6)
    tokens_before = before.get("tokens") or {}
    tokens_after = after.get("tokens") or {}
    tokens = {}
    for key in ("input", "output", "reasoning"):
        if isinstance(tokens_before.get(key), int) and isinstance(tokens_after.get(key), int):
            tokens[key] = tokens_after[key] - tokens_before[key]
    result: Dict[str, Any] = {}
    if cost is not None:
        result["cost"] = cost
    if tokens:
        result["tokens"] = tokens
    return result


def last_assistant_text(session_id: str, api=_run_api) -> str:
    body = api(
        "GET",
        f"/api/session/{session_id}/message",
        {"limit": 1, "order": "desc", "type": "assistant"},
    )
    messages = (body or {}).get("data", []) or []
    if not messages:
        return ""
    parts = messages[0].get("content", []) or []
    chunks = [p.get("text", "") for p in parts if p.get("type") == "text" and p.get("text")]
    return "\n".join(chunks).strip()


# --------------------------------------------------------------------------- #
# peer context (read-only) and SME
# --------------------------------------------------------------------------- #

def context_block(peer: Dict[str, Any], focus_ticket: Optional[str] = None) -> str:
    """Summarise the peer's progress.json without writing to it."""
    log_dir = peer.get("logDir")
    if not log_dir:
        return ""
    progress_file = Path(log_dir).expanduser() / "progress.json"
    try:
        progress = json.loads(progress_file.read_text())
    except (OSError, json.JSONDecodeError):
        return ""
    tickets = progress.get("tickets", []) or []
    in_progress = [t.get("id") for t in tickets if t.get("status") == "in-progress"]
    pending_high = [
        t.get("id") for t in tickets
        if t.get("status") == "pending" and t.get("priority") == "high"
    ]
    parts = []
    if in_progress:
        parts.append("in-progress " + ", ".join(in_progress[:4]))
    if focus_ticket:
        parts.append(f"focus {focus_ticket}")
    elif pending_high:
        parts.append("pending high " + ", ".join(pending_high[:4]))
    last = (progress.get("humanLog") or [])[-1:]
    if last and last[0].get("message"):
        parts.append(f'last "{last[0]["message"][:80]}"')
    if progress.get("lastMode"):
        parts.append(f"mode {progress['lastMode']}")
    return "; ".join(parts)


def _manifest_stack(directory: Path) -> List[str]:
    stack: List[str] = []
    pyproject = directory / "pyproject.toml"
    if pyproject.exists():
        text = pyproject.read_text(errors="ignore")
        name = re.search(r'^name\s*=\s*"([^"]+)"', text, re.MULTILINE)
        deps = re.search(r"dependencies\s*=\s*\[(.*?)\]", text, re.DOTALL)
        if name:
            stack.append(name.group(1))
        if deps:
            found = re.findall(r'"([A-Za-z0-9_.-]+)', deps.group(1))
            if found:
                stack.append("pyproject: " + ", ".join(found[:6]))
    requirements = directory / "requirements.txt"
    if requirements.exists():
        deps = [
            line.split("=")[0].split(">")[0].strip()
            for line in requirements.read_text(errors="ignore").splitlines()
            if line.strip() and not line.startswith("#")
        ]
        if deps:
            stack.append("requirements: " + ", ".join(deps[:6]))
    package_json = directory / "package.json"
    if package_json.exists():
        try:
            pkg = json.loads(package_json.read_text())
            deps = list((pkg.get("dependencies") or {}).keys())[:6]
            stack.append("node: " + ", ".join(deps) if deps else "node")
        except json.JSONDecodeError:
            stack.append("node (package.json unreadable)")
    if (directory / "Cargo.toml").exists():
        stack.append("rust (cargo)")
    if (directory / "go.mod").exists():
        first = (directory / "go.mod").read_text(errors="ignore").splitlines()[:1]
        stack.append(first[0] if first else "go")
    return stack


def _purpose(directory: Path) -> str:
    pyproject = directory / "pyproject.toml"
    if pyproject.exists():
        text = pyproject.read_text(errors="ignore")
        desc = re.search(r'^description\s*=\s*"([^"]+)"', text, re.MULTILINE)
        if desc:
            return desc.group(1)
    package_json = directory / "package.json"
    if package_json.exists():
        try:
            desc = json.loads(package_json.read_text()).get("description")
            if desc:
                return desc
        except json.JSONDecodeError:
            pass
    readme = next((p for p in directory.glob("README*")), None)
    if readme:
        for line in readme.read_text(errors="ignore").splitlines():
            line = line.strip().lstrip("#").strip()
            if line:
                return line[:120]
    return "unknown"


def _modules(directory: Path, limit: int = 8) -> List[str]:
    entries = []
    for child in sorted(directory.iterdir(), key=lambda p: p.name.lower()):
        if child.name in SKIP_DIRS or child.name.startswith("."):
            continue
        if child.is_dir():
            entries.append(child.name + "/")
    return entries[:limit]


def _tests_hint(directory: Path) -> str:
    hints = []
    for name in ("tests", "test", "__tests__", "spec"):
        if (directory / name).is_dir():
            hints.append(name + "/")
    if (directory / "pytest.ini").exists() or (directory / "pyproject.toml").exists():
        return "pytest -q (" + ", ".join(hints or ["tests"]) + ")"
    if (directory / "package.json").exists():
        return "npm test"
    if (directory / "Cargo.toml").exists():
        return "cargo test"
    if (directory / "go.mod").exists():
        return "go test ./..."
    return "unknown (" + ", ".join(hints) + ")" if hints else "unknown"


def _entry_points(directory: Path) -> List[str]:
    candidates = [
        "app/main.py", "main.py", "src/main.py", "manage.py",
        "src/index.ts", "src/index.js", "index.ts", "index.js",
        "cmd/server/main.go",
    ]
    found = [c for c in candidates if (directory / c).exists()]
    return found or ["unknown"]


def quick_sme(alias: str, directory: Path, limit: int = 8) -> str:
    stack = _manifest_stack(directory)
    lines = [
        f"# Peer SME: {alias}",
        "",
        f"- Directory: `{directory}`",
        f"- Generated: {now_iso()}",
        "",
        "## Purpose",
        _purpose(directory),
        "",
        "## Stack",
        *(f"- {item}" for item in (stack or ["unknown"])),
        "",
        "## Entry points",
        *(f"- {item}" for item in _entry_points(directory)),
        "",
        "## Modules",
        *(f"- {item}" for item in (_modules(directory, limit=limit) or ["unknown"])),
        "",
        "## Tests",
        f"- {_tests_hint(directory)}",
        "",
        "> Read-only snapshot. Never written into the peer repo.",
    ]
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# messaging
# --------------------------------------------------------------------------- #

def scan_secrets(text: str) -> List[str]:
    return [pattern.pattern for pattern in SECRET_PATTERNS if pattern.search(text)]


def envelope(
    peer_alias: str,
    request: str,
    *,
    project: str,
    ticket: Optional[str],
    turn: int,
    budget: int,
    thread: str,
    context: str = "",
) -> str:
    header = f"[devcadence peer] alias={peer_alias} from={project}"
    if ticket:
        header += f" ticket={ticket}"
    header += f" turn={turn}/{budget}"
    lines = [header]
    if context:
        lines.append(f"context: {context}")
    lines.append(f"request: {request}")
    lines.append(
        "boundaries: no edites tu repo, progress.json, logs ni tickets salvo "
        "pedido explícito. Respondé en esta sesión; si algo no lo podés "
        "verificar, decilo."
    )
    return "\n".join(lines)


def _thread_sends(thread: str, path: Optional[Path] = None) -> int:
    path = path or exchanges_path()
    if not path.exists():
        return 0
    count = 0
    for line in path.read_text(errors="ignore").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("type") == "send" and record.get("thread") == thread:
            count += 1
    return count


def _append_exchange(record: Dict[str, Any], log_dir: Optional[Path] = None) -> None:
    path = exchanges_path(log_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _project_name() -> str:
    override = os.environ.get("PROGRESS_JSON", "")
    candidates = []
    if override:
        candidates.append(Path(override).expanduser())
    candidates.append(Path.cwd() / "progress.json")
    for candidate in candidates:
        try:
            return json.loads(candidate.read_text()).get("project") or Path.cwd().name
        except (OSError, json.JSONDecodeError):
            continue
    return Path.cwd().name


def send_peer(
    alias: str,
    text: str,
    *,
    delivery: str = "queue",
    ticket: Optional[str] = None,
    thread: Optional[str] = None,
    turns: Optional[int] = None,
    wait: bool = False,
    timeout: int = DEFAULT_WAIT_TIMEOUT,
    use_context: bool = True,
    focus_ticket: Optional[str] = None,
    allow_secrets: bool = False,
    new_thread: bool = False,
    registry: Optional[Path] = None,
    log_dir: Optional[Path] = None,
    api=_run_api,
) -> Dict[str, Any]:
    if delivery not in ("queue", "steer"):
        raise PeerError("delivery must be 'queue' or 'steer'")
    peer = get_peer(alias, registry)
    budget = int(turns or peer.get("turnBudget") or DEFAULT_TURNS)
    date = now_iso()[:10]
    thread = thread or f"{alias}-{date}"
    if new_thread:
        thread = f"{thread}-{uuid.uuid4().hex[:6]}"

    used = _thread_sends(thread, exchanges_path(log_dir))
    if used >= budget:
        raise PeerError(
            f"turn budget exhausted for thread '{thread}' ({used}/{budget}). "
            "Review the last reply, then continue with --new-thread."
        )

    if not allow_secrets:
        hits = scan_secrets(text)
        if hits:
            raise PeerError(
                "outgoing text looks like it contains secrets; remove them or pass "
                "--allow-secrets"
            )

    session_id = resolve_session(peer, api=api)
    context = context_block(peer, focus_ticket) if use_context else ""
    turn = used + 1
    body_text = envelope(
        alias, text.strip(), project=_project_name(), ticket=ticket,
        turn=turn, budget=budget, thread=thread, context=context,
    )
    message_id = "msg_" + uuid.uuid4().hex
    before = _copy_metrics(_metrics(session_id, api=api))

    payload = {
        "id": message_id,
        "text": body_text,
        "delivery": delivery,
        "metadata": {
            "devcadence": {
                "alias": alias,
                "from": _project_name(),
                "ticket": ticket,
                "turn": turn,
                "budget": budget,
                "thread": thread,
            }
        },
    }
    response = api("POST", f"/api/session/{session_id}/prompt", data=payload)
    returned = ((response or {}).get("data") or {}).get("id") or message_id

    reply = None
    if wait:
        wait_for_session(session_id, timeout=timeout, api=api)
        reply = last_assistant_text(session_id, api=api)

    after = _copy_metrics(_metrics(session_id, api=api))
    record = {
        "id": "ex-" + uuid.uuid4().hex[:12],
        "type": "send",
        "thread": thread,
        "alias": alias,
        "turn": turn,
        "budget": budget,
        "ticket": ticket,
        "sessionId": session_id,
        "messageId": returned,
        "delivery": delivery,
        "sentAt": now_iso(),
        "request": text.strip(),
        "context": context,
        "response": reply,
        "cost": _metrics_delta(before, after),
        "verified": False,
    }
    _append_exchange(record, log_dir)
    return record


def wait_for_session(session_id: str, timeout: int = DEFAULT_WAIT_TIMEOUT, api=_run_api) -> None:
    api("POST", f"/api/experimental/session/{session_id}/wait", timeout=timeout)


def read_peer(
    alias: str,
    *,
    wait: bool = False,
    timeout: int = DEFAULT_WAIT_TIMEOUT,
    registry: Optional[Path] = None,
    log_dir: Optional[Path] = None,
    api=_run_api,
) -> Dict[str, Any]:
    peer = get_peer(alias, registry)
    session_id = resolve_session(peer, api=api)
    if wait:
        wait_for_session(session_id, timeout=timeout, api=api)
    text = last_assistant_text(session_id, api=api)
    record = {
        "id": "ex-" + uuid.uuid4().hex[:12],
        "type": "reply",
        "alias": alias,
        "sessionId": session_id,
        "readAt": now_iso(),
        "response": text,
    }
    _append_exchange(record, log_dir)
    return record


def retract_peer(
    alias: str,
    message_id: str,
    *,
    registry: Optional[Path] = None,
    api=_run_api,
) -> None:
    peer = get_peer(alias, registry)
    session_id = resolve_session(peer, api=api)
    api("DELETE", f"/api/session/{session_id}/inbox/{message_id}")


# --------------------------------------------------------------------------- #
# registration
# --------------------------------------------------------------------------- #

def _is_git_repo(directory: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "-C", str(directory), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def add_peer(
    alias: str,
    directory: str,
    *,
    log_dir: Optional[str] = None,
    session_id: Optional[str] = None,
    turns: int = DEFAULT_TURNS,
    sme: str = "quick",
    registry: Optional[Path] = None,
    sme_path: Optional[Path] = None,
    require_git: bool = True,
    api=_run_api,
) -> Dict[str, Any]:
    alias = alias.strip().lower()
    if not ALIAS_RE.match(alias):
        raise PeerError(
            "alias must be 2-31 chars: lowercase letters, digits, '-' or '_', "
            "starting with a letter or digit"
        )
    peers = load_registry(registry)
    if alias in peers:
        raise PeerError(f"peer '{alias}' already exists; remove it first or pick another alias")

    root = _expand(directory)
    if not root.is_dir():
        raise PeerError(f"directory does not exist: {root}")
    if require_git and not _is_git_repo(root):
        raise PeerError(f"not a git repository: {root}")

    peer_log_dir = Path(log_dir).expanduser() if log_dir else Path.home() / "docs" / root.name
    sessions = list_sessions(root, api=api)
    if session_id:
        get_session(session_id, api=api)  # raises if it does not exist
    elif sessions:
        session_id = sessions[0]["id"]
    else:
        raise PeerError(f"no opencode session found in {root} — open opencode there once")

    entry: Dict[str, Any] = {
        "alias": alias,
        "directory": str(root),
        "logDir": str(peer_log_dir),
        "sessionId": session_id,
        "sessionTitle": sessions[0].get("title") if sessions else None,
        "turnBudget": int(turns),
        "sessionVerified": False,
        "addedAt": now_iso(),
    }

    if sme != "skip":
        target = sme_path or (sme_dir() / f"{alias}.md")
        _atomic_write(target, quick_sme(alias, root))
        entry["smePath"] = str(target)

    peers[alias] = entry
    save_registry(peers, registry)
    return entry


def remove_peer(alias: str, *, registry: Optional[Path] = None) -> None:
    peers = load_registry(registry)
    if alias not in peers:
        raise PeerError(f"unknown peer '{alias}'")
    peers.pop(alias)
    save_registry(peers, registry)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _print_peers(peers: Dict[str, Dict[str, Any]]) -> None:
    if not peers:
        print("No peers registered. Run: /devcadence peer add <alias>")
        return
    print(f"{'Alias':16} {'Turns':6} {'Session':24} Directory")
    print("-" * 92)
    for alias, peer in sorted(peers.items()):
        print(
            f"{alias:16} {peer.get('turnBudget', DEFAULT_TURNS):<6} "
            f"{(peer.get('sessionId') or '-')[:24]:24} {peer.get('directory', '?')}"
        )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Message another opencode agent (DevCadence peer)")
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="Register a peer")
    add.add_argument("alias", nargs="?")
    add.add_argument("--directory", "-d")
    add.add_argument("--log-dir")
    add.add_argument("--session")
    add.add_argument("--turns", type=int, default=DEFAULT_TURNS)
    add.add_argument("--sme", choices=["quick", "full", "skip"], default="quick")
    add.add_argument("--yes", "-y", action="store_true", help="Non-interactive")
    add.add_argument("--no-git-check", action="store_true")

    sub.add_parser("list", help="List registered peers")

    rm = sub.add_parser("remove", help="Remove a peer")
    rm.add_argument("alias")

    send = sub.add_parser("send", help="Send a request to a peer")
    send.add_argument("alias")
    send.add_argument("text", nargs="+")
    send.add_argument("--delivery", choices=["queue", "steer"], default="queue")
    send.add_argument("--ticket")
    send.add_argument("--thread")
    send.add_argument("--turns", type=int)
    send.add_argument("--wait", action="store_true")
    send.add_argument("--timeout", type=int, default=DEFAULT_WAIT_TIMEOUT)
    send.add_argument("--no-context", action="store_true")
    send.add_argument("--context-ticket")
    send.add_argument("--allow-secrets", action="store_true")
    send.add_argument("--new-thread", action="store_true")
    send.add_argument("--json", action="store_true")

    read = sub.add_parser("read", help="Read the peer's last assistant message")
    read.add_argument("alias")
    read.add_argument("--wait", action="store_true")
    read.add_argument("--timeout", type=int, default=DEFAULT_WAIT_TIMEOUT)
    read.add_argument("--json", action="store_true")

    wait = sub.add_parser("wait", help="Block until the peer session is idle")
    wait.add_argument("alias")
    wait.add_argument("--timeout", type=int, default=DEFAULT_WAIT_TIMEOUT)

    retract = sub.add_parser("retract", help="Cancel a queued message")
    retract.add_argument("alias")
    retract.add_argument("message_id")

    ctx = sub.add_parser("context", help="Show the context block for a peer")
    ctx.add_argument("alias")
    ctx.add_argument("--ticket")

    discover = sub.add_parser("discover", help="List sessions in a directory")
    discover.add_argument("--directory", "-d", default=".")

    args = parser.parse_args(argv)

    try:
        if args.command == "add":
            alias = args.alias
            directory = args.directory
            if not alias:
                if not sys.stdin.isatty():
                    raise PeerError("alias is required: peer add <alias> --directory <path>")
                alias = input("Alias: ").strip()
            if not directory:
                if not sys.stdin.isatty():
                    raise PeerError("--directory is required")
                directory = input(f"Repo directory for '{alias}': ").strip()
            entry = add_peer(
                alias, directory, log_dir=args.log_dir, session_id=args.session,
                turns=args.turns, sme=args.sme, require_git=not args.no_git_check,
            )
            print(f"Registered peer '{entry['alias']}'")
            print(f"  directory: {entry['directory']}")
            print(f"  log dir:   {entry['logDir']}")
            print(f"  session:   {entry['sessionId']} ({entry.get('sessionTitle') or 'untitled'})")
            print(f"  turns:     {entry['turnBudget']} per request")
            if entry.get("smePath"):
                print(f"  SME:       {entry['smePath']}")
            print("\nTry: ask " + entry["alias"] + " to review DC-43 and estimate the work")
        elif args.command == "list":
            _print_peers(load_registry())
        elif args.command == "remove":
            remove_peer(args.alias)
            print(f"Removed peer '{args.alias}'")
        elif args.command == "send":
            record = send_peer(
                args.alias, " ".join(args.text), delivery=args.delivery,
                ticket=args.ticket, thread=args.thread, turns=args.turns,
                wait=args.wait, timeout=args.timeout,
                use_context=not args.no_context, focus_ticket=args.context_ticket,
                allow_secrets=args.allow_secrets, new_thread=args.new_thread,
            )
            if args.json:
                print(json.dumps(record, indent=2, ensure_ascii=False))
            else:
                print(f"queued to {args.alias}: {record['messageId']} (turn {record['turn']}/{record['budget']})")
                if record.get("context"):
                    print(f"  context: {record['context']}")
                if record.get("response"):
                    print("\n" + record["response"])
                elif not args.wait:
                    print(f"  not waiting. Later: /devcadence peer read {args.alias}")
        elif args.command == "read":
            record = read_peer(args.alias, wait=args.wait, timeout=args.timeout)
            if args.json:
                print(json.dumps(record, indent=2, ensure_ascii=False))
            elif record.get("response"):
                print(record["response"])
            else:
                print(f"No assistant text yet from {args.alias}.")
        elif args.command == "wait":
            peer = get_peer(args.alias)
            wait_for_session(resolve_session(peer), timeout=args.timeout)
            print(f"{args.alias} is idle.")
        elif args.command == "retract":
            retract_peer(args.alias, args.message_id)
            print(f"retracted {args.message_id} from {args.alias}")
        elif args.command == "context":
            print(context_block(get_peer(args.alias), args.ticket) or "(no context)")
        elif args.command == "discover":
            sessions = list_sessions(_expand(args.directory))
            if not sessions:
                print("No sessions found.")
            for session in sessions:
                print(f"{session['id']}  {session.get('title', 'untitled')}")
    except PeerError as exc:
        print(f"peer: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
