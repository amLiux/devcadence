---
description: Structured dev workflow with DevCadence protocol (standup/pair/review/checkout)
agent: build
---

skill({ name: "devcadence" })

Activate DevCadence protocol for current project.

## Agent Instructions

1. **Read** this entire command file on every `/devcadence` invocation.
2. **Read** `SECURITY.md` from the project root if it exists, before generating code or running commands.
3. **All script commands** in this file are relative to the project root. Use the project root as working directory unless explicitly noted.
4. **Do not guess paths.** Use the exact file paths declared in the File Manifest below.
5. **Maintain logs and progress.json** automatically. The user should never have to ask "did you log this?"

## Project Root

The project root is the directory containing this command file's parent `.opencode/` directory. For this installation:

```
/Users/amliux/Dev/devdock
```

All file paths below are relative to this root.

## File Manifest

These are the canonical files and directories DevCadence uses. Do not rely on globbing or inference.

| Path | Purpose |
|------|---------|
| `.opencode/commands/devcadence.md` | This command file (loaded by opencode) |
| `.opencode/skills/devcadence/SKILL.md` | Full protocol specification |
| `scripts/tickets.py` | Ticket query utility |
| `scripts/logs.py` | Log query utility |
| `scripts/progress.py` | Progress snapshot utility |
| `scripts/storage.py` | SQLite index builder/query |
| `scripts/update.py` | DevCadence update checker/applier |
| `scripts/migrate.py` | Migration assistant (optional deps) |
| `~/docs/devdock/progress.json` | Project state (tickets, humanLog, observations) |
| `~/docs/devdock/logs/` | Session logs |
| `~/docs/devdock/.devcadence.db` | SQLite index (auto-built) |
| `SECURITY.md` | Project security context (read if present) |

## Usage

```
/devcadence <mode> [args]
```

### Modes

| Mode | Purpose | Tone | Writes log |
|------|---------|------|------------|
| `standup` | Define today's tasks, create/update tickets | Normal | Yes |
| `pair` | Passive coding help, answers, decisions | Caveman Full | Yes |
| `review` | Check code against ticket acceptance criteria | Caveman Full | Yes |
| `checkout` | Wrap up session, update progress, estimate remaining | Normal | Yes |
| `huddle` | Lightweight ideation, standalone, no chain requirement | Normal | Yes |

### Utility modes (standalone, no log, no chain validation)

| Mode | Exact command | Purpose |
|------|---------------|---------|
| `config` | `/devcadence config` | View/edit project config |
| `note` | `/devcadence note "<message>"` | Quick humanLog entry |
| `extensions` | `/devcadence extensions` | List sibling commands |
| `new-extension` | `/devcadence new-extension` | Scaffold sibling command |
| `migrate` | `uv run python scripts/migrate.py ...` | Export/import project data |
| `storage` | `python scripts/storage.py` | Build/update SQLite index |
| `update` | `python scripts/update.py --check` / `--apply` | Check/apply upstream updates |

## Running scripts

All scripts live in `scripts/` at project root. Always run from project root.

```bash
# Run from /Users/amliux/Dev/devdock
python scripts/tickets.py --all
python scripts/logs.py --days 7
python scripts/progress.py
python scripts/progress.py --usage

# Build or refresh SQLite index
python scripts/storage.py

# Query with SQLite (default)
python scripts/tickets.py --all

# Force JSON fallback
python scripts/tickets.py --no-sqlite --all
```

Scripts use SQLite by default for fast indexed queries. The SQLite index is `.devcadence.db` next to `progress.json`. JSON files remain canonical. Pass `--no-sqlite` to bypass the index.

## Update

`/devcadence update` — check for or apply upstream DevCadence updates.

**Exact commands (run from project root):**

```bash
# Check if updates are available (read-only, safe)
python scripts/update.py --check

# Apply updates after explicit confirmation
python scripts/update.py --apply

# Apply updates without prompting (use with care)
python scripts/update.py --apply --yes
```

`scripts/update.py` wraps `update.sh`. It never modifies files in `--check` mode. On successful `--apply`, it appends a `humanLog` entry to `progress.json`.

## Migration

`/devcadence migrate` — move DevCadence project data between machines.

**Exact commands (run from project root):**

```bash
# Install optional deps first
uv sync --extra migrate

# List discoverable projects
uv run python scripts/migrate.py discover

# Export to encrypted file
uv run python scripts/migrate.py export <project> -o project.dcm

# Export and serve over network
uv run python scripts/migrate.py export <project> --serve

# Import from transfer code
uv run python scripts/migrate.py import <transfer-code> <target-dir>

# Import from encrypted file
uv run python scripts/migrate.py import --file project.dcm --key <key> <target-dir>
```

Serve mode starts a temporary FastAPI endpoint on the source machine, serves the encrypted archive once, and shuts down. The transfer code contains the endpoint, token, and decryption key. The API never sees plaintext.

## Per-Project Config

Add a `# Project Config` block to this file to set log dir, progress path, ticket format, and custom modes. If absent, the agent prompts with a setup form on first `standup`.

```markdown
# Project Config
# - Log dir: ~/docs/my-project/
# - Progress: ~/docs/my-project/progress.json
# - Ticket format: PROJ-01
# - Git control: manual
# - User role: dev-lead
# - Caveman level: full
```

## Mode Chain

Default chain:

```
checkout → standup → pair → review → checkout
huddle → standup | pair | checkout | huddle
```

Modes can be skipped. `review` is commonly skipped. The agent checks `lastMode` on start and warns if the transition is unusual but never blocks.

## Rules

1. **Read from declared files only.** Use the File Manifest above. Do not grep/glob for files.
2. **Each mode reads from the previous mode in the chain.** `checkout` → `standup` → `pair` → `review` → `checkout`.
3. **Global logs** (`global: true`) are scanned on every mode start.
4. **On review approval:** auto-update `progress.json`, advance ticket, append to `humanLog`.
5. **Pair and review use Caveman Full mode** (terse, ~55% token reduction).
6. **Standup, checkout, and huddle use Normal tone**.
7. **Utility modes** (`config`, `note`, `extensions`, `new-extension`, `migrate`, `storage`, `update`) are standalone — no log, no chain validation.
8. **Never push to main** unless `git.control` is `total`. Branches always start from latest main.
9. **Tickets persist immediately.** Whenever a new ticket is discussed or scoped, write it to `progress.json > tickets[]` in the same response.
10. **Optional log metadata:** agents may write `metadata.model` and `metadata.usage` when the runtime exposes them via env vars (`OPENCODE_MODEL`, `OPENCODE_USAGE_*`). Omit if unavailable.
11. **Security:** read `SECURITY.md` at project root on every session start and apply its rules before generating code.
