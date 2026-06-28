---
name: devcadence
description: Structured AI collaboration protocol with standup/pair/review/checkout/huddle modes, standardized logs, and developer behavioral observations
license: MIT
compatibility: opencode
metadata:
  audience: developers
  workflow: collaboration
---

# DevCadence Protocol

AI collaboration workflow with 5 modes (standup/pair/review/checkout/huddle), standardized logs, and developer growth tracking.

## Log Schema

All logs use this schema:

```json
{
  "id": "YYYY-MM-DD-<mode>",
  "mode": "standup|pair|review|checkout|huddle",
  "timestamp": "ISO8601",
  "phase": 1,
  "ticketIds": ["XXX-01"],
  "global": false,
  "human": {
    "summary": "One-line summary",
    "notes": "Detailed human-readable notes"
  },
  "machine": {
    "context": "Technical context, decisions, blockers",
    "nextAction": "What to do next"
  },
  "observations": [],
  "references": []
}
```

## Mode Chain

Default chain:

```
flowchart LR
  standup-->pair
  pair-->review
  review-->checkout
  standup-->checkout
  pair-->checkout
  huddle-->standup
  huddle-->pair
  huddle-->checkout
```

Modes can be skipped (review is commonly skippable). Agent checks last mode on start and warns if chain is unusual but never blocks.

### Bootstrap (First Run)

On first `/devcadence` invocation in a project, check for project config:

1. **Check** if command file (`.opencode/commands/devcadence.md`) has a `# Project Config` block with: log dir, progress path, ticket format, custom modes
2. **Also check** `progress.json` at default location `~/docs/<project>/progress.json` — if exists, project is already configured
3. **If no config found**, present a setup form:

   ```
   No DevCadence config found for this project.
   
   ┌─ Project Config ──────────────────────────────────┐
   │ Log dir:      ~/docs/<project>/                   │
   │ Progress:     ~/docs/<project>/progress.json      │
   │ Ticket ID:    PROJ-01                             │
   │ Custom modes: (optional) e.g. skip review         │
   │ Git control:  manual / branch / total             │
   └───────────────────────────────────────────────────┘
   
   Accept defaults or provide values.
   ```

4. **Wire collected values** into `.opencode/commands/devcadence.md` as a `# Project Config` block (or append to existing command)
5. **Create** `progress.json` with these values on first standup log write

This runs once. On subsequent invocations, config block exists and is read directly.

### Standup
- **Writes:** ticket, tasks, acceptance criteria
- **Purpose:** "What are we doing today?"
- **Tone:** Normal
- **Caveman:** No
- **Branch (control=branch/total):** At end, ask "Create branch {prefix}/{ticketId}?" If yes, create from main. Auto if control=total.

### Pair
- **Writes:** key decisions, discoveries, blockers
- **Purpose:** User codes, AI answers (passive unless critical flag)
- **Tone:** Caveman Full
- **Caveman:** Yes
- **Proactive:** Deprecated API or paradigm mismatch? Flag immediately.
- **Auto-logging:** Every meaningful exchange auto-updates the pair log in real-time. Agent owns log management — user should never ask "did you log this?" If no new info, agent says nothing. If a decision, observation, or blocker emerges, agent writes it immediately without being prompted.
- **Commits (control=branch/total):** On user request or after completing acceptance criteria, commit on current branch using commitTemplate. control=total commits without asking, control=branch asks first.

### Review
- **Writes:** approve/request changes, observations
- **Purpose:** Quality check against ticket acceptance criteria
- **Tone:** Caveman Full
- **Caveman:** Yes
- **On approval:** Update progress.json, advance ticket, append humanLog. If git configured, squash-merge branch or create PR.
- **Observations:** Track developer patterns for growth feedback
- **Diff check:** Read git diff on branch against acceptance criteria. Flag any mismatch.

### Checkout
- **Writes:** progress update, remaining estimate, prep for next standup
- **Purpose:** Wrap up, estimate what's left
- **Tone:** Normal
- **Caveman:** No
- **Reads:** git diff + status for accurate progress. If branch active, suggest PR or squash-merge.

### Huddle

- **Writes:** huddle log, humanLog entries, observations, creates/updates tickets (mandatory)
- **Purpose:** "I had an idea" — lightweight ideation without spinning the full cycle
- **Tone:** Normal (default), adapts to persona mapping
- **Caveman:** No (follows persona)
- **Chain:** Standalone — no required predecessor. Updates `lastMode` to huddle so chain knows it happened. Any mode can follow.

**Wizard flow:**

```
/devcadence huddle

┌─ Huddle ───────────────────────────────────────────┐
│ How many days to scan for context? [7]              │
│ Tags (comma-sep, e.g. bug, infra, idea): idea       │
│ Global? (y/n) [n]                                   │
│ Describe your thoughts...                            │
└────────────────────────────────────────────────────┘
```

**Tag → Persona mapping** (configurable via project config):

| Tag | Persona |
|-----|---------|
| `bug` | Critical Response engineer — root cause analysis, minimal reproduction, fix strategy |
| `infra` | Senior DevOps engineer — scalability, reliability, cost, observability |
| `frontend` | Frontend architect — UX, component design, accessibility, bundle perf |
| `backend` | Backend architect — API design, data flow, query perf, type safety |
| `idea` | Innovation partner — explore possibilities, rapid prototyping, thought experiments |
| *(custom)* | *(custom persona set via /devcadence config)* |

**Behavior:**
1. On start, scan last N days of logs from `<log-dir>/logs/` for context
2. Run wizard: days-back, tags, global flag
3. Set agent persona based on first tag match (ordered priority)
4. Free-form discussion. Agent captures in real-time:
   - Key decisions → humanLog entries
   - Emerging patterns → observations
   - Concrete tasks → new tickets in progress.json
5. **On close — mandatory updates:**
   - Write huddle log (with `global: true` if flagged)
   - Append humanLog entry to progress.json
   - Persist all observations captured during discussion
   - Save any new/updated tickets
   - Update `lastMode` to huddle
6. **On close — suggest next mode:**
   - If concrete tasks emerged → suggest `pair` to implement
   - If ideas need more structure → suggest `standup` to plan them
   - If blockers or bugs surfaced → suggest `standup` to create a ticket
   - If nothing actionable → suggest closing
   - If user wants to keep discussing → offer to continue or close

**Natural pathways:**
```
huddle --> pair       (concrete tasks, let's build)
huddle --> standup    (needs planning, create tickets)
huddle --> checkout   (session over, wrap up)
huddle --> huddle     (more ideas, keep riffing)
```

**Capabilities:**
- Create tickets with task, acceptance criteria, files
- Add humanLog entries (type: checkpoint, decision, blocker, observation, milestone)
- Add observations with pattern, severity, confidence
- Edit existing tickets (status, AC, notes)
- Tag itself `global: true` so ideas surface automatically

## Utility Modes

Standalone modes outside the chain. No log written — they modify meta-config, not project work.

### Config

`/devcadence config` — View and edit project configuration.

1. **Read** current `# Project Config` block from the command file (`.opencode/commands/devcadence.md`) and `progress.json`
2. **Present** a pre-filled form:

   ```
   ┌─ Project Config ──────────────────────────────────┐
   │ Log dir:      ~/docs/my-project/                  │
   │ Progress:     ~/docs/my-project/progress.json     │
   │ Ticket:       PROJ-01                             │
   │ Git control:  branch (manual / branch / total)    │
   │ Caveman:      full (lite / full / ultra)          │
   │ Branch prefix: feat                               │
    │ Commit tmpl:  #{ticketId} {message}               │
   │ Huddle tags:  bug:Critical Response engineer...   │
   │              infra:Senior DevOps engineer...      │
   │              (edit in progress.json)              │
   └───────────────────────────────────────────────────┘
   ```

3. **On save:** Rewrite the `# Project Config` block in the command file and update `progress.json` with the new values
4. **Append** a `humanLog` entry noting the change

### Extensions

`/devcadence extensions` — List all sibling commands that extend DevCadence.

1. **Scan** `.opencode/commands/*.md` for files containing `skill({ name: "devcadence" })`
2. **Exclude** `devcadence.md` itself
3. **Extract** from each match:
   - Command name (filename without `.md`)
   - `description` field from frontmatter
   - Any additional `skill({ name: "..." })` lines (other loaded skills)
   - Purpose line (the sentence after `Activate DevCadence protocol for...`)
4. **Display** as a formatted list:

   ```
   DevCadence Extensions
   ─────────────────────
   hortus-migration — HortusClavis IAM migration with HC SME
     Skills: devcadence, hc-migrate
     Use: /hortus-migration standup

   No extensions found. Run /devcadence new-extension to create one.
   ```

### New Extension

`/devcadence new-extension` — Scaffold a new sibling command that extends DevCadence with a domain SME.

1. **Ask** interactively:

   ```
   ┌─ New Extension ───────────────────────────────────┐
   │ Command name:      hortus-migration               │
   │ Description:       HortusClavis IAM migration     │
   │ Skill(s) to load:  hc-migrate (comma-sep)         │
   │ Purpose:           HC auth migration with fallback │
   └───────────────────────────────────────────────────┘
   ```

2. **Read** the parent `devcadence.md` to copy its `# Project Config` block
3. **Create** `.opencode/commands/<name>.md`:

   ```markdown
   # ---
   # description: <description>
   # agent: build
   # ---

   skill({ name: "devcadence" })
   skill({ name: "<skill-1>" })
   skill({ name: "<skill-n>" })
   Activate DevCadence protocol for <purpose>.

   ## Project Config
   # - Log dir: <copied from parent>
   # - Progress: <copied from parent>
   # - Ticket format: <copied from parent>
   ```

4. **Check** if the skill file exists at `.opencode/skills/<name>/SKILL.md`. If not, suggest creating it:

   ```
   Skill "hc-migrate" not found in .opencode/skills/.
   Copy it from the source repo or create a new SKILL.md.
   ```

5. **Log** the creation as a humanLog entry

### New SME

`/devcadence new-sme` — Auto-generate a repo SME at `.opencode/skills/<name>/SKILL.md` for any agent dropped into this repo. SME is standalone — usable without DevCadence.

**Wizard flow:**

```
/devcadence new-sme

┌─ New SME ───────────────────────────────────────────┐
│ SME name:           <repo>-sme (auto)               │
│ Analysis depth:     quick / full [quick]            │
│ Link to DevCadence? y/n [y]                          │
└──────────────────────────────────────────────────────┘
```

**Analysis depth:**

Quick mode (default, zero deps):
1. `tree -L 3` for directory structure
2. `rg` (ripgrep) for key patterns: API routes, DB schemas, entry points, imports
3. Read key config files (package.json, pyproject.toml, Cargo.toml, etc.)
4. Agent synthesizes → ~1000 token SKILL.md

Full mode (adds graphify + repomix):
1. Same as quick mode
2. `npx repomix --compress` — tree-sitter signature extraction (function/class signatures only)
3. Run graphify for knowledge graph with community clusters
4. Enriched SKILL.md with call graphs + dependency maps

**Output SKILL.md format:**

```markdown
---
name: <repo>-sme
description: Auto-generated SME for <repo>
---

# SME: <repo>

## Overview
<2-3 lines describing repo purpose>

## Entry Points
- src/main.py — FastAPI app, port 8000
- src/cli/index.ts — CLI entry

## Key Modules
- src/api/ — REST endpoints (12 routes)
- src/models/ — DB schemas (8 tables)

## Key Dependencies
- FastAPI, SQLAlchemy, Redis

## Architecture
- Monorepo: apps/ + packages/
- API Gateway → Services → PostgreSQL
```

**Integration:**
- SME is written to `.opencode/skills/<name>/SKILL.md` — usable by any agent, any framework
- If "Link to DevCadence?" is yes, runs `new-extension` to create a command loading `devcadence + <repo>-sme`
- SME is user-owned — editable, versionable, shareable across projects

**Design principle:** "Compass, not encyclopedia" (Meta, 2026). Output is ~1000 tokens — small enough to always include.

## File Locations

Default location: `~/docs/<project>/`. Configurable per-project via `# Project Config` block in the command file.

```
<log-dir>/
├── logs/
│   ├── YYYY-MM-DD-standup.json
│   ├── YYYY-MM-DD-pair.json
│   ├── YYYY-MM-DD-review.json
│   ├── YYYY-MM-DD-checkout.json
│   └── YYYY-MM-DD-huddle.json
├── progress.json
└── plan.md
```

Agent resolves `<log-dir>` from project config. Fallback: `~/docs/<project>/`.

## Progress Schema

```json
{
  "project": "<project-name>",
  "currentPhase": 1,
  "currentTicketIds": ["XXX-01"],
  "lastMode": "checkout",
  "cavemanMode": "full",
  "git": {
    "control": "manual|branch|total",
    "repo": "owner/repo",
    "branchPrefix": "feat",
    "commitTemplate": "#{ticketId} {message}"
  },
  "workflow": {
    "diagram": "flowchart LR\n  standup-->pair\n  pair-->review\n  review-->checkout\n  standup-->checkout\n  pair-->checkout",
    "skippable": ["review"],
    "defaultStart": "standup"
  },
  "tickets": [
    {
      "id": "XXX-01",
      "phase": 1,
      "task": "Description",
      "files": ["path/to/file.ts"],
      "acceptance": ["Criterion 1"],
      "status": "pending|in-progress|completed",
      "createdAt": "ISO8601",
      "completedAt": null,
      "reviewStatus": null
    }
  ],
  "huddleTags": {
    "bug": "Critical Response engineer — root cause, minimal repro, fix",
    "infra": "Senior DevOps — scalability, reliability, cost",
    "frontend": "Frontend architect — UX, components, a11y, perf",
    "backend": "Backend architect — API design, data flow, perf",
    "idea": "Innovation partner — explore, riff, rapid prototype"
  },
  "humanLog": [
    {
      "id": "hl-001",
      "type": "checkpoint|decision|blocker|observation|milestone",
      "logRef": "YYYY-MM-DD-<mode>",
      "message": "Quick human-readable summary",
      "timestamp": "ISO8601",
      "phase": 1,
      "ticketIds": ["XXX-01"],
      "author": "agent|user",
      "tags": ["tag1"]
    }
  ],
  "observations": [
    {
      "id": "obs-001",
      "pattern": "Description of observed coding pattern",
      "severity": "blocker|warning|suggestion|praise",
      "confidence": "emerging|established|confirmed",
      "ticketIds": ["XXX-01"],
      "suggestion": "What to do instead",
      "firstSeen": "ISO8601",
      "timesObserved": 1
    }
  ]
}
```

## humanLog vs logs/

- **logs/*.json** — Full conversation record. Machine-readable for AI context. One per mode invocation.
- **progress.json > humanLog** — Digest/summary of important moments. One-liner per entry, links to full log via `logRef`. Designed for external API consumption (FastAPI dashboard, PM reports).

On each mode's log creation, append a `humanLog` entry to progress.json.

## Observations (Developer Growth)

Observations track coding patterns across sessions. Structure supports `/devcadence 1:1` command:

- Review mode adds observations when patterns emerge
- `confidence` upgrades: emerging → established (3+ times) → confirmed (user acknowledged)
- `/devcadence 1:1` reads all observations across projects, groups by pattern, ranks by severity × frequency
- Output: personalized growth plan with resources (books, courses, docs)

## Git Control Levels

| Level | Branch Creation | Commits | Push to main |
|-------|----------------|---------|--------------|
| `manual` | Agent suggests, you run | You write | You decide |
| `branch` | Agent asks at standup end | Agent commits with template, asks | Never. PR only |
| `total` | Auto on standup | Agent commits + pushes directly | Yes (solo dev) |

- **control=manual**: no git automation. Agent just reads git status for context.
- **control=branch**: standup creates branch from main (with ask). Pair commits on branch with `commitTemplate`. Review checks diff. Checkout suggests PR/merge.
- **control=total**: same as branch but no asking — auto on everything.

## Rules

1. **Mode chain flexible** — default standup→pair→review→checkout. Skippable modes allowed. Agent warns on unusual transitions but does not block.
2. **Global flag** — any log with `"global": true` scanned on every mode start for critical decisions.
3. **Ticket IDs** — array format. Multiple tickets per log.
4. **Observations** — review mode tracks developer patterns for growth feedback.
5. **Auto-update** — on review approval, update progress.json status, advance ticket, append to humanLog.
6. **Caveman Full** — pair and review modes use terse, fragment-style communication.
7. **Auto-logging** — logs are the agent's responsibility, not the user's. Every mode silently updates its log file as context accumulates. User never asks "did you log this?"
8. **Git safety** — never push to main unless `control=total`. Branches always start from latest main.
9. **Huddle standalone** — huddle mode is outside the mode chain. It updates `lastMode` but no mode requires huddle and huddle requires no mode.

## Extending DevCadence

This protocol is designed to be extended. Two ways to configure:

**Manual:** Add a `# Project Config` block to your command file:

```markdown
skill({ name: "devcadence" })

# Project Config
# - Log dir: ~/docs/my-project/
# - Progress: ~/docs/my-project/progress.json
# - Ticket format: MYPRJ-01
```

**Auto (Bootstrap):** Run `/devcadence standup` with no config. AI detects missing config, presents a setup form, and wires values into the command file automatically.

For custom workflow chains, override `workflow.diagram` in progress.json after first standup.

Future modes: `/devcadence 1:1`, `/devcadence retrospective`, `/devcadence release`

Huddle mode: `/devcadence huddle` — see [Huddle](#huddle) above.

Utility modes: `config`, `extensions`, `new-extension` — see [Utility Modes](#utility-modes) above.

## Caveman Mode

Pair and review modes use caveman Full style:
- Drop articles (a, an, the)
- Use fragments
- Direct, no filler
- Same technical accuracy, ~55% fewer tokens

Normal: "The component is re-rendering because you're creating a new object reference each render"
Caveman: "Component re-renders. New object ref each render. Wrap in useMemo."
