---
description: Structured dev workflow with DevCadence protocol (standup/pair/review/checkout)
agent: build
---

skill({ name: "devcadence" })

Activate DevCadence protocol for current project.

## Usage

/devcadence <mode> [args]

Modes:
- standup — define today's tasks, create ticket
- pair — passive mode, answer questions, caveman Full
- review — check code against ticket, approve or request changes
- checkout — wrap up, update progress, estimate remaining

Utilities (outside chain, no log):
- config — view/edit project config (log dir, git control, etc.)
- extensions — list sibling commands that extend DevCadence
- new-extension — scaffold a new sibling command with domain SME

## Per-Project Config

Add a `# Project Config` block to this file to set log dir, progress path, ticket format, and custom modes. If absent, AI prompts with a setup form on first standup.

```
# Project Config
# - Log dir: ~/docs/my-project/
# - Progress: ~/docs/my-project/progress.json
# - Ticket format: PROJ-01
```

## Rules

- Each mode reads from previous in chain: checkout → standup → pair → review → checkout
- Global logs (global: true) scanned on every mode start
- On review approval: auto-update progress.json + advance ticket + append to humanLog
- Pair and review use caveman Full mode (terse, ~55% token reduction)
- Standup and checkout use normal tone
- Utility modes (config/extensions/new-extension) are standalone — no log, no chain validation
- Optional log metadata: agents may write `metadata.model` and `metadata.usage` when the runtime exposes them (env vars: `OPENCODE_MODEL`, `OPENCODE_USAGE_*`). Omit if unavailable.
