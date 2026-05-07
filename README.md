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

Or manual: copy `skills/devcadence/SKILL.md` to `.opencode/skills/devcadence/SKILL.md` in your project.

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
