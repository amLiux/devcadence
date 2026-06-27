# DevCadence

Structured AI collaboration protocol with standup/pair/review/checkout modes, standardized logs, and developer behavioral observations.

## Setup

```bash
# Clone
git clone https://github.com/amLiux/devcadence.git
cd devcadence

# Install skill (opencode)
npx skills add devcadence
```

Or manual: copy `skills/devcadence/` to `.opencode/skills/devcadence/` in your project.

## Usage

See the DevCadence protocol in `skills/devcadence/SKILL.md` for full documentation.

Quick start:
- `/devcadence standup` — start a session
- `/devcadence pair` — code with caveman support
- `/devcadence review` — check work
- `/devcadence checkout` — wrap up

## Project Configuration

Each project needs a config block so the AI knows where to store logs, what tickets to use, and which modes apply.

Add to your project command (`.opencode/commands/devcadence.md`):

```markdown
# .opencode/commands/devcadence.md
skill({ name: "devcadence" })

# Project Config
# - Log dir: ~/docs/my-project/
# - Progress: ~/docs/my-project/progress.json
# - Ticket format: MYPRJ-01
# - Modes: standup → pair → checkout (skip review)
```

If no config found on `/devcadence standup`, the AI prompts with a setup form to collect these details and wires them into the command.

### Config Fields

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `Log dir` | Yes | `~/docs/<project>/` | Where per-session logs (`YYYY-MM-DD-<mode>.json`) are stored |
| `Progress` | Yes | `<log-dir>/progress.json` | Tracks tickets, humanLog, observations |
| `Ticket format` | Yes | `PROJ-01` | Prefix used for ticket IDs (e.g. `MYPRJ-01`, `XXX-42`) |
| `Custom modes` | No | standup→pair→review→checkout | Custom workflow chain, skip modes, add future modes |

## Extending with Examples

### Pattern: base + specialist commands

Keep `devcadence.md` pure (just workflow). Create sibling commands for specific tasks that load DevCadence + a domain SME.

```
.opencode/commands/
├── devcadence.md           # skill({ name: "devcadence" }) — general dev
└── hortus-migration.md     # skill({ name: "devcadence" }) + skill({ name: "hc-migrate" })
└── next-migration.md       # skill({ name: "devcadence" }) + skill({ name: "next-migrate" })
```

All commands in the same project share the same `# Project Config` block (log dir, progress, tickets). Use `/devcadence standup` for general work, `/hortus-migration standup` for HC-specific sessions.

### Simple: migration project (FE + BE)

```markdown
# .opencode/commands/migrate.md
# ---
# description: Migration workflow with DevCadence
# ---

skill({ name: "devcadence" })
Activate DevCadence protocol for monolith migration.

## Project Config
# - Log dir: ~/docs/big-migration/
# - Progress: ~/docs/big-migration/progress.json
# - Ticket format: MIG-01
```

### Real: DevCadence + HortusClavis IAM

Two files sharing the same config:

```markdown
# .opencode/commands/devcadence.md
skill({ name: "devcadence" })
Activate DevCadence for JardinBinario-be.

## Project Config
# - Log dir: ~/docs/JardinBinario-be/
# - Progress: ~/docs/JardinBinario-be/progress.json
# - Ticket format: JARDIN-01
```

```markdown
# .opencode/commands/hortus-migration.md
skill({ name: "devcadence" })
skill({ name: "hc-migrate" })
Activate DevCadence + HC SME for JardinBinario-be auth migration.

## Project Config
# - Log dir: ~/docs/JardinBinario-be/
# - Progress: ~/docs/JardinBinario-be/progress.json
# - Ticket format: JARDIN-01
```

See [`examples/devcadence-hortus-integration.md`](examples/devcadence-hortus-integration.md) for the full files.

### Adding custom modes

Override the default workflow chain by setting `workflow.diagram` in `progress.json` after first standup:

```json
{
  "workflow": {
    "diagram": "flowchart LR\n  standup-->pair\n  pair-->checkout",
    "skippable": ["review"],
    "defaultStart": "standup"
  }
}
```

## Architecture

```
devcadence/
├── skills/devcadence/SKILL.md   # Protocol definition (single source of truth)
├── commands/devcadence.md       # Base invocation command
├── tests/                       # Schema validation
├── examples/                    # Example usage for different projects
├── install.sh                   # One-liner for any agent
├── LICENSE                      # MIT
└── README.md
```

## License

MIT
