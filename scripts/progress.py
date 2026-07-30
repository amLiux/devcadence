#!/usr/bin/env python3
"""DevCadence progress snapshot — show current project state at a glance."""

import json
import os
import sys
from pathlib import Path

PROGRESS_PATH = os.environ.get("PROGRESS_JSON", "")
DEFAULT_LOCATIONS = [
    Path.home() / "docs" / "devcadence" / "progress.json",
    Path("progress.json"),
]


def find_progress():
    if PROGRESS_PATH and Path(PROGRESS_PATH).exists():
        return Path(PROGRESS_PATH)
    for p in DEFAULT_LOCATIONS:
        if p.exists():
            return p
    return None


def load_progress(path):
    with open(path) as f:
        return json.load(f)


def load_log_usage(log_dir):
    """Aggregate token usage from log metadata. Returns (total, per_ticket)."""
    totals = {"prompt": 0, "completion": 0, "total": 0}
    per_ticket = {}
    if not log_dir.is_dir():
        return totals, per_ticket
    for f in sorted(log_dir.glob("*.json")):
        try:
            with open(f) as fh:
                log = json.load(fh)
        except (json.JSONDecodeError, IOError):
            continue
        usage = log.get("metadata", {}).get("usage")
        if not usage:
            continue
        try:
            prompt = int(usage.get("prompt_tokens", 0) or 0)
            completion = int(usage.get("completion_tokens", 0) or 0)
            total = int(usage.get("total_tokens", 0) or 0)
        except (ValueError, TypeError):
            continue
        totals["prompt"] += prompt
        totals["completion"] += completion
        totals["total"] += total
        for ticket_id in log.get("ticketIds", []):
            if ticket_id not in per_ticket:
                per_ticket[ticket_id] = {"prompt": 0, "completion": 0, "total": 0}
            per_ticket[ticket_id]["prompt"] += prompt
            per_ticket[ticket_id]["completion"] += completion
            per_ticket[ticket_id]["total"] += total
    return totals, per_ticket


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Show DevCadence project progress")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    parser.add_argument("--usage", action="store_true", help="Show token usage from logs")
    args = parser.parse_args()

    path = find_progress()
    if not path:
        print("progress.json not found. Set PROGRESS_JSON or run from project root.", file=sys.stderr)
        sys.exit(1)

    data = load_progress(path)

    if args.json:
        print(json.dumps(data, indent=2, default=str))
        return

    project = data.get("project", "?")
    phase = data.get("currentPhase", "?")
    last_mode = data.get("lastMode", "?")
    role = data.get("userRole", "?")
    caveman = data.get("cavemanMode", "?")
    git = data.get("git", {})

    tickets = data.get("tickets", [])
    pending = [t for t in tickets if t.get("status") == "pending"]
    in_progress = [t for t in tickets if t.get("status") == "in-progress"]
    completed = [t for t in tickets if t.get("status") == "completed"]

    print(f"\n{'=' * 50}")
    print(f"  DevCadence: {project}")
    print(f"{'=' * 50}")
    print(f"  Phase:       {phase}")
    print(f"  Last mode:   {last_mode}")
    print(f"  Role:        {role}")
    print(f"  Caveman:     {caveman}")
    print(f"  Git:         {git.get('control', 'manual')} ({git.get('repo', 'unknown')})")
    print()

    if in_progress:
        print("  In Progress:")
        for t in in_progress:
            pri = t.get("priority", "medium").upper()
            print(f"    [{pri:6}] {t['id']:30} {t.get('task', '')}")
        print()

    if pending:
        print("  Pending (by priority):")
        PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
        sorted_pending = sorted(pending, key=lambda t: PRIORITY_ORDER.get(t.get("priority", "medium"), 1))
        for t in sorted_pending:
            pri = t.get("priority", "medium").upper()
            print(f"    [{pri:6}] {t['id']:30} {t.get('task', '')}")
        print()

    print(f"  Completed: {len(completed)}")
    print(f"  Total:     {len(tickets)}")

    human_log = data.get("humanLog", [])
    if human_log:
        recent = human_log[-3:]
        print(f"\n  Recent activity:")
        for entry in recent:
            print(f"    {entry.get('timestamp', '')[:10]}  {entry.get('message', '')[:70]}")

    if args.usage:
        log_dir = path.parent / "logs"
        totals, per_ticket = load_log_usage(log_dir)
        print(f"\n  Token usage (from log metadata):")
        print(f"    Total:    prompt={totals['prompt']}, completion={totals['completion']}, total={totals['total']}")
        if per_ticket:
            print(f"    By ticket:")
            for ticket_id, u in sorted(per_ticket.items()):
                print(f"      {ticket_id}: prompt={u['prompt']}, completion={u['completion']}, total={u['total']}")

    print()


if __name__ == "__main__":
    main()
