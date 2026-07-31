#!/usr/bin/env python3
"""DevCadence log utility — search logs by date, mode, ticket ID."""

import json
import os
import sys
from pathlib import Path

LOG_DIR = os.environ.get("DEVCADENCE_LOG_DIR", "")
DEFAULT_LOCATIONS = [
    Path.home() / "docs" / "devcadence" / "logs",
    Path("logs"),
]


def find_log_dir():
    if LOG_DIR and Path(LOG_DIR).is_dir():
        return Path(LOG_DIR)
    for p in DEFAULT_LOCATIONS:
        if p.is_dir():
            return p
    return None


def load_logs(log_dir):
    logs = []
    for f in sorted(log_dir.glob("*.json")):
        try:
            with open(f) as fh:
                data = json.load(fh)
                data["_file"] = f.name
                logs.append(data)
        except (json.JSONDecodeError, IOError):
            continue
    return logs


def filter_logs(logs, mode=None, ticket_id=None, days=None, global_only=False):
    result = logs
    if mode:
        result = [l for l in result if l.get("mode") == mode]
    if ticket_id:
        result = [l for l in result if ticket_id in l.get("ticketIds", [])]
    if global_only:
        result = [l for l in result if l.get("global")]
    if days:
        from datetime import datetime, timedelta
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        result = [l for l in result if l.get("timestamp", "") >= cutoff]
    return result


def format_log(log):
    mode = log.get("mode", "?")
    ts = log.get("timestamp", "?")[:10]
    summary = log.get("human", {}).get("summary", "No summary")
    tickets = ", ".join(log.get("ticketIds", [])) or "none"
    return f"  {ts}  {mode:10}  {tickets:30}  {summary}"


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Search DevCadence logs")
    parser.add_argument("--mode", choices=["standup", "pair", "review", "checkout", "huddle"], help="Filter by mode")
    parser.add_argument("--ticket", help="Filter by ticket ID")
    parser.add_argument("--days", type=int, help="Last N days only")
    parser.add_argument("--global-only", action="store_true", help="Show only global logs")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    parser.add_argument("--full", action="store_true", help="Show full log details")
    args = parser.parse_args()

    log_dir = find_log_dir()
    if not log_dir:
        print("Logs directory not found. Set DEVCADENCE_LOG_DIR or run from project root.", file=sys.stderr)
        sys.exit(1)

    logs = load_logs(log_dir)
    logs = filter_logs(logs, mode=args.mode, ticket_id=args.ticket, days=args.days, global_only=args.global_only)

    if args.json:
        print(json.dumps(logs, indent=2, default=str))
        return

    if not logs:
        print("No logs match filters.")
        return

    if args.full:
        for log in logs:
            print(f"\n{'=' * 60}")
            print(f"  File: {log.get('_file')}")
            print(f"  Mode: {log.get('mode')}  Date: {log.get('timestamp', '')[:10]}")
            print(f"  Tickets: {', '.join(log.get('ticketIds', [])) or 'none'}")
            print(f"  Summary: {log.get('human', {}).get('summary', '')}")
            print(f"  Notes: {log.get('human', {}).get('notes', '')}")
            if log.get("machine", {}).get("nextAction"):
                print(f"  Next: {log['machine']['nextAction']}")
            print()
    else:
        print(f"\n{'Date':12} {'Mode':10} {'Tickets':32} Summary")
        print("-" * 90)
        for log in logs:
            print(format_log(log))
        print(f"\n  {len(logs)} log(s) found.\n")


if __name__ == "__main__":
    main()
