#!/usr/bin/env python3
"""DevCadence ticket utility — filter, sort, display tickets from progress.json."""

import json
import os
import sys
from pathlib import Path

PROGRESS_PATH = os.environ.get("PROGRESS_JSON", "")
DEFAULT_LOCATIONS = [
    Path.home() / "docs" / "devcadence" / "progress.json",
    Path("progress.json"),
]

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


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


def sort_tickets(tickets):
    return sorted(tickets, key=lambda t: PRIORITY_ORDER.get(t.get("priority", "medium"), 1))


def filter_tickets(tickets, status=None, priority=None, phase=None):
    result = tickets
    if status:
        result = [t for t in result if t.get("status") == status]
    if priority:
        result = [t for t in result if t.get("priority") == priority]
    if phase is not None:
        result = [t for t in result if t.get("phase") == phase]
    return result


def format_ticket(t, verbose=False):
    pri = t.get("priority", "medium").upper()
    status = t.get("status", "unknown")
    tid = t.get("id", "?")
    task = t.get("task", "No description")
    line = f"  [{pri:6}] {tid:30} {status:12} {task}"
    if verbose:
        ac = t.get("acceptance", [])
        if ac:
            line += "\n" + "\n".join(f"          - {c}" for c in ac)
    return line


def main():
    import argparse

    parser = argparse.ArgumentParser(description="List/filter DevCadence tickets")
    parser.add_argument("--status", choices=["pending", "in-progress", "completed", "cancelled"], help="Filter by status")
    parser.add_argument("--priority", choices=["high", "medium", "low"], help="Filter by priority")
    parser.add_argument("--phase", type=int, help="Filter by phase")
    parser.add_argument("--all", action="store_true", help="Show all tickets (default: pending + in-progress only)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show acceptance criteria")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    path = find_progress()
    if not path:
        print("progress.json not found. Set PROGRESS_JSON or run from project root.", file=sys.stderr)
        sys.exit(1)

    data = load_progress(path)
    tickets = data.get("tickets", [])

    if not args.all and not args.status:
        tickets = [t for t in tickets if t.get("status") in ("pending", "in-progress")]

    tickets = filter_tickets(tickets, status=args.status, priority=args.priority, phase=args.phase)
    tickets = sort_tickets(tickets)

    if args.json:
        print(json.dumps(tickets, indent=2))
        return

    if not tickets:
        print("No tickets match filters.")
        return

    print(f"\n{'Priority':8} {'ID':32} {'Status':12} Task")
    print("-" * 80)
    for t in tickets:
        print(format_ticket(t, verbose=args.verbose))
    print()


if __name__ == "__main__":
    main()
