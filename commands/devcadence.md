---
description: DevCadence protocol dispatcher
agent: build
---

skill({ name: "devcadence" })

# /devcadence <mode>

When the user invokes `/devcadence <mode>`, run that mode immediately. Do not ask for confirmation unless the mode itself requires it. Full protocol, File Manifest, and detailed rules are in the loaded `devcadence` skill (`SKILL.md`).

## Modes

| Mode | Purpose | Tone |
|------|---------|------|
| `standup` | Plan today, create/update tickets | Normal |
| `pair` | Deep work, answer questions | Caveman Full |
| `review` | Check code against ticket acceptance criteria | Caveman Full |
| `checkout` | Wrap up session, update progress | Normal |
| `huddle` | Standalone ideation | Normal |

## Utilities (standalone, no log, no chain validation)

| Mode | Command |
|------|---------|
| `config` | `/devcadence config` |
| `note` | `/devcadence note "<message>"` |
| `extensions` | `/devcadence extensions` |
| `new-extension` | `/devcadence new-extension` |
| `migrate` | `uv run python scripts/migrate.py ...` |
| `storage` | `python scripts/storage.py` |
| `update` | `python scripts/update.py --check` / `--apply` |

## Agent rules

1. Work from project root: `/Users/amliux/Dev/devdock`
2. Scripts live in `scripts/` — always run as `python3 scripts/<file>.py ...`
3. Read `SECURITY.md` from project root if it exists
4. Auto-update `progress.json` and write session logs — never ask the user
5. For exact file paths, read the File Manifest in the `devcadence` skill
6. Never push to main unless `git.control` is `total`

# Project Config

```markdown
# - Log dir: ~/docs/devdock/
# - Progress: ~/docs/devdock/progress.json
# - Ticket format: dd-01
# - Git control: manual
# - User role: dev-lead
# - Caveman level: full
```
