# AGENTS.md — DevCadence Project

This project uses DevCadence protocol to build itself.

## Quick Reference
- Skill: `skills/devcadence/SKILL.md` — the protocol
- Command: `commands/devcadence.md` — base invocation
- Progress: `~/docs/devcadence/progress.json`
- Logs: `~/docs/devcadence/logs/`

## Build
```bash
pip install -e ".[dev]"
pytest tests/
```

## DevCadence Self-Building
When modifying the protocol, use `/devcadence standup` to define the task, then `/devcadence pair` to refine, `/devcadence review` to check, and `/devcadence checkout` to log progress. The protocol must remain consistent with its own schema — every schema change in SKILL.md must be reflected in progress.json examples.
