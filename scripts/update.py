#!/usr/bin/env python3
"""DevCadence update utility.

Check for updates from the upstream GitHub repository and optionally apply them
via update.sh. Never modifies files without explicit user intent.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import List, Optional

REPO_RAW = "https://raw.githubusercontent.com/amLiux/devcadence/main"

# Files managed by update.sh. When DevCadence is installed in a project, files
# live under .opencode/. When working on the devcadence repo itself, source files
# live at the repo root.
MANAGED_FILES = [
    ".opencode/skills/devcadence/SKILL.md",
    ".opencode/commands/devcadence.md",
    "skills/devcadence/SKILL.md",
    "commands/devcadence.md",
    "scripts/tickets.py",
    "scripts/logs.py",
    "scripts/progress.py",
    "scripts/storage.py",
    "scripts/update.py",
    "scripts/migrate.py",
]


def _progress_locations() -> List[Path]:
    env = os.environ.get("PROGRESS_JSON", "")
    if env:
        return [Path(env)]
    return [
        Path.home() / "docs" / "devcadence" / "progress.json",
        Path("progress.json"),
    ]


def find_progress() -> Optional[Path]:
    for p in _progress_locations():
        if p.exists():
            return p
    return None


def _remote_url(local_path: str) -> str:
    return f"{REPO_RAW}/{local_path}"


def _fetch(url: str) -> Optional[bytes]:
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return resp.read()
    except Exception:
        return None


def _hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _read_local(path: Path) -> Optional[bytes]:
    try:
        return path.read_bytes()
    except (OSError, IOError):
        return None


def _backup_config(cmd_path: Path) -> str:
    """Extract the # Project Config block from the command file."""
    try:
        text = cmd_path.read_text()
    except (OSError, IOError):
        return ""
    lines = text.splitlines()
    capture = False
    out = []
    for line in lines:
        if line.strip() == "# Project Config":
            capture = True
        if capture:
            out.append(line)
    return "\n".join(out)


def check_updates() -> dict:
    """Return status of managed files without modifying anything."""
    results = {}
    for local_path in MANAGED_FILES:
        local = Path(local_path)
        remote = _fetch(_remote_url(local_path))
        local_content = _read_local(local)

        if remote is None:
            results[local_path] = {"status": "unavailable", "reason": "failed to fetch remote"}
            continue

        if local_content is None:
            results[local_path] = {"status": "missing", "reason": "local file not found"}
            continue

        if _hash(local_content) == _hash(remote):
            results[local_path] = {"status": "up-to-date"}
        else:
            results[local_path] = {"status": "update-available"}
    return results


def print_check(results: dict) -> int:
    available = [p for p, r in results.items() if r["status"] == "update-available"]
    missing = [p for p, r in results.items() if r["status"] == "missing"]
    unavailable = [p for p, r in results.items() if r["status"] == "unavailable"]
    up_to_date = [p for p, r in results.items() if r["status"] == "up-to-date"]

    print("\nDevCadence update check")
    print("=" * 50)

    if unavailable:
        print("\nCould not reach upstream:")
        for p in unavailable:
            print(f"  ✗ {p}")

    if missing:
        print("\nMissing locally (would be created on apply):")
        for p in missing:
            print(f"  → {p}")

    if available:
        print("\nUpdates available:")
        for p in available:
            print(f"  → {p}")

    if up_to_date:
        print("\nUp to date:")
        for p in up_to_date:
            print(f"  ✓ {p}")

    print()
    return len(available) + len(missing)


def apply_update(dry_run: bool = False) -> bool:
    """Run update.sh. If update.sh is missing, fetch it to a temp file first."""
    import tempfile

    update_sh = Path("update.sh")
    temp_path = None

    if not update_sh.exists():
        remote = _fetch(f"{REPO_RAW}/update.sh")
        if remote is None:
            print("update.sh not found locally and could not be fetched from upstream.", file=sys.stderr)
            return False
        if dry_run:
            print("Would fetch update.sh from upstream and run it.")
            return True
        with tempfile.NamedTemporaryFile(mode="wb", suffix="-update.sh", delete=False) as tmp:
            tmp.write(remote)
            temp_path = Path(tmp.name)
        temp_path.chmod(0o755)
        update_sh = temp_path
    elif dry_run:
        print("Would run: bash update.sh")
        return True

    try:
        result = subprocess.run(
            ["bash", str(update_sh)],
            check=True,
            text=True,
        )
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"update.sh failed with exit code {e.returncode}.", file=sys.stderr)
        return False
    except FileNotFoundError:
        print("bash not found. Cannot run update.sh.", file=sys.stderr)
        return False
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()


def _next_human_log_id(human_log: list) -> str:
    if not human_log:
        return "hl-001"
    nums = []
    for entry in human_log:
        eid = entry.get("id", "")
        if eid.startswith("hl-"):
            try:
                nums.append(int(eid.split("-")[1]))
            except (ValueError, IndexError):
                continue
    next_num = max(nums, default=0) + 1
    return f"hl-{next_num:03d}"


def append_update_human_log(progress_path: Path, changed_count: int) -> None:
    try:
        data = json.loads(progress_path.read_text())
    except (json.JSONDecodeError, OSError):
        return

    human_log = data.get("humanLog", [])
    new_entry = {
        "id": _next_human_log_id(human_log),
        "type": "milestone",
        "logRef": None,
        "message": f"DevCadence updated via /devcadence update --apply. {changed_count} file(s) changed or verified.",
        "timestamp": _iso_now(),
        "phase": data.get("currentPhase", 1),
        "ticketIds": [],
        "author": "user",
        "tags": ["update", "milestone"],
    }
    human_log.append(new_entry)
    data["humanLog"] = human_log
    progress_path.write_text(json.dumps(data, indent=2))


def _iso_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    parser = argparse.ArgumentParser(description="Check for and apply DevCadence updates")
    parser.add_argument("--check", action="store_true", help="Check for updates without modifying files")
    parser.add_argument("--apply", action="store_true", help="Apply updates via update.sh (requires confirmation)")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt (use with care)")
    args = parser.parse_args()

    if not args.check and not args.apply:
        args.check = True

    if args.check:
        results = check_updates()
        pending = print_check(results)
        sys.exit(0 if pending == 0 else 1)

    if args.apply:
        # First check what would change
        results = check_updates()
        pending = sum(
            1 for r in results.values() if r["status"] in ("update-available", "missing")
        )

        if pending == 0:
            print("Nothing to update.")
            sys.exit(0)

        print(f"\n{pending} file(s) will be updated by update.sh.")
        if not args.yes:
            try:
                answer = input("Apply update? [y/N]: ")
            except (EOFError, KeyboardInterrupt):
                answer = "n"
            if answer.strip().lower() != "y":
                print("Update cancelled.")
                sys.exit(0)

        if apply_update():
            progress_path = find_progress()
            if progress_path:
                append_update_human_log(progress_path, pending)
            print("Update complete.")
            sys.exit(0)
        else:
            sys.exit(1)


if __name__ == "__main__":
    main()
