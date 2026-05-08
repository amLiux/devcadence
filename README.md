# DevCadence

DevCadence builds itself. This repo uses the same protocol it defines — check progress, run standups, review, checkout.

## Setup

```bash
# Clone
git clone https://github.com/<your>/devcadence.git
cd devcadence

# Install skill (opencode)
npx skills add devcadence
```

Or manual: copy `skills/devcadence/` to `.opencode/skills/devcadence/` in your project.

## Self-Development

DevCadence builds itself. The `.opencode/` folder in this repo enables recursive development — edit the protocol using the protocol. Source files in `skills/` and `commands/` are mirrored to `.opencode/` for auto-discovery. Run `/devcadence` from this repo to work on DevCadence itself.

## Usage

See the DevCadence protocol in `skills/devcadence/SKILL.md` for full documentation.

Quick start:
- `/devcadence standup` — start a session
- `/devcadence pair` — code with caveman support
- `/devcadence review` — check work
- `/devcadence checkout` — wrap up

## Extending

Create a project-specific command that references the skill:

```bash
# .opencode/commands/migrate.md
skill({ name: "devcadence" })
Activate DevCadence for <project> migration.
```

## Architecture

```
devcadence/
├── .opencode/
│   ├── skills/devcadence/SKILL.md   # Auto-discovered by opencode (self-development)
│   └── commands/devcadence.md       # /devcadence works inside this repo
├── skills/devcadence/SKILL.md       # Source of truth (distribution copy)
├── commands/devcadence.md           # Source of truth (distribution copy)
├── tests/                           # Schema validation
├── examples/                        # Example usage for different projects
├── install.sh                       # One-liner for any agent
├── LICENSE                          # MIT
└── README.md
```

## License

MIT
