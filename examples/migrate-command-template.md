# Example: Migration project command
# Place in .opencode/commands/migrate.md

# ---
# description: Migration workflow with DevCadence
# agent: build
# ---

skill({ name: "devcadence" })
Activate DevCadence protocol for monolith migration.

## Project Config
# - Log dir: ~/docs/big-migration/
# - Progress: ~/docs/big-migration/progress.json
# - Ticket format: MIG-01
#
# Custom workflow: skip review, use standup → pair → checkout
