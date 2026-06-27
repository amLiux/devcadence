# Example: DevCadence + HortusClavis Migration (specialist command pattern)

File 1: `.opencode/commands/devcadence.md` — base workflow
```markdown
# ---
# description: Structured dev workflow with DevCadence protocol
# agent: build
# ---

skill({ name: "devcadence" })
Activate DevCadence protocol for JardinBinario-be backend development.

## Project Config
# - Log dir: ~/docs/JardinBinario-be/
# - Progress: ~/docs/JardinBinario-be/progress.json
# - Ticket format: JARDIN-01
# - Git control: branch
```

File 2: `.opencode/commands/hortus-migration.md` — specialist (loads base + SME)
```markdown
# ---
# description: HortusClavis IAM migration with DevCadence + HC SME
# agent: build
# ---

skill({ name: "devcadence" })
skill({ name: "hc-migrate" })
Activate DevCadence protocol for JardinBinario-be HC auth migration.

## Project Config
# - Log dir: ~/docs/JardinBinario-be/
# - Progress: ~/docs/JardinBinario-be/progress.json
# - Ticket format: JARDIN-01
# - Git control: branch
```

Both share same `# Project Config` block so logs, tickets, and progress are unified across commands.
Use `/devcadence standup` for general dev work, `/hortus-migration standup` for HC-specific sessions.
