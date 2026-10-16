#!/usr/bin/env python3
"""DevCadence progress snapshot — show current project state at a glance."""

import json
import os
import sys
from pathlib import Path

from storage import aggregate_usage, find_progress, get_progress_summary, get_recent_human_log, get_tickets, try_sync

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
    parser.add_argument("--no-sqlite", action="store_true", help="Force JSON fallback instead of SQLite index")
    args = parser.parse_args()

    path = find_progress()
    if not path:
        print("progress.json not found. Set PROGRESS_JSON or run from project root.", file=sys.stderr)
        sys.exit(1)

    conn = try_sync(path, no_sqlite=args.no_sqlite)
    if conn:
        if args.json:
            # For raw JSON, still read canonical progress.json
            data = load_progress(path)
            print(json.dumps(data, indent=2, default=str))
            return
        data = load_progress(path)
        summary = get_progress_summary(conn)
        recent = get_recent_human_log(conn, limit=3)
    else:
        data = load_progress(path)
        if args.json:
            print(json.dumps(data, indent=2, default=str))
            return
        tickets = data.get("tickets", [])
        summary = {
            "total": len(tickets),
            "pending": len([t for t in tickets if t.get("status") == "pending"]),
            "in_progress": len([t for t in tickets if t.get("status") == "in-progress"]),
            "completed": len([t for t in tickets if t.get("status") == "completed"]),
        }
        recent = data.get("humanLog", [])[-3:]

    project = data.get("project", "?")
    phase = data.get("currentPhase", "?")
    last_mode = data.get("lastMode", "?")
    role = data.get("userRole", "?")
    caveman = data.get("cavemanMode", "?")
    git = data.get("git", {})

    print(f"\n{'=' * 50}")
    print(f"  DevCadence: {project}")
    print(f"{'=' * 50}")
    print(f"  Phase:       {phase}")
    print(f"  Last mode:   {last_mode}")
    print(f"  Role:        {role}")
    print(f"  Caveman:     {caveman}")
    print(f"  Git:         {git.get('control', 'manual')} ({git.get('repo', 'unknown')})")
    print()

    if summary["in_progress"]:
        print("  In Progress:")
        if conn:
            in_progress_tickets = get_tickets(conn, status="in-progress")
            PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
            in_progress_tickets = sorted(in_progress_tickets, key=lambda t: PRIORITY_ORDER.get(t.get("priority", "medium"), 1))
        else:
            in_progress_tickets = [t for t in data.get("tickets", []) if t.get("status") == "in-progress"]
        for t in in_progress_tickets:
            pri = t.get("priority", "medium").upper()
            print(f"    [{pri:6}] {t['id']:30} {t.get('task', '')}")
        print()

    if summary["pending"]:
        print("  Pending (by priority):")
        if conn:
            pending_tickets = get_tickets(conn, status="pending")
            PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
            pending_tickets = sorted(pending_tickets, key=lambda t: PRIORITY_ORDER.get(t.get("priority", "medium"), 1))
        else:
            PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
            pending_tickets = sorted(
                [t for t in data.get("tickets", []) if t.get("status") == "pending"],
                key=lambda t: PRIORITY_ORDER.get(t.get("priority", "medium"), 1),
            )
        for t in pending_tickets:
            pri = t.get("priority", "medium").upper()
            print(f"    [{pri:6}] {t['id']:30} {t.get('task', '')}")
        print()

    print(f"  Completed: {summary['completed']}")
    print(f"  Total:     {summary['total']}")

    if recent:
        print(f"\n  Recent activity:")
        for entry in recent:
            print(f"    {entry.get('timestamp', '')[:10]}  {entry.get('message', '')[:70]}")

    if args.usage:
        if conn:
            totals, per_ticket = aggregate_usage(conn)
        else:
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
