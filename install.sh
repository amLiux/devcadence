#!/usr/bin/env bash
set -euo pipefail

# DevCadence Installer
# Fetches skill from GitHub and installs into your project.
# Usage: curl -sL https://raw.githubusercontent.com/amLiux/devcadence/main/install.sh | bash

REPO_RAW="https://raw.githubusercontent.com/amLiux/devcadence/main"
STEP=0

log() {
  STEP=$((STEP + 1))
  echo "[$STEP] $1"
}

indent() {
  echo "    $1"
}

ok() {
  indent "✓ $1"
}

fail() {
  indent "✗ $1"
  exit 1
}

echo ""
echo "DevCadence Installer"
echo "===================="
echo "Target:  $(pwd)"
echo ""

# [1] Create .opencode directory
log "Setting up .opencode/..."
if [ -d ".opencode" ]; then
  ok "Found"
else
  indent "→ Creating .opencode/"
  mkdir -p ".opencode"
  ok "Created"
fi

# [2] Create .opencode/skills directory
log "Setting up .opencode/skills/..."
if [ -d ".opencode/skills" ]; then
  ok "Found"
else
  indent "→ Creating .opencode/skills/"
  mkdir -p ".opencode/skills"
  ok "Created"
fi

# [3] Create .opencode/commands directory
log "Setting up .opencode/commands/..."
if [ -d ".opencode/commands" ]; then
  ok "Found"
else
  indent "→ Creating .opencode/commands/"
  mkdir -p ".opencode/commands"
  ok "Created"
fi

# [4] Create skill directory
log "Setting up .opencode/skills/devcadence/..."
mkdir -p ".opencode/skills/devcadence"
ok "Ready"

# [5] Fetch SKILL.md
log "Installing SKILL.md..."
if curl -sf "$REPO_RAW/skills/devcadence/SKILL.md" -o ".opencode/skills/devcadence/SKILL.md"; then
  ok "Downloaded"
else
  fail "Failed to download SKILL.md — check your internet connection"
fi

# [6] Fetch command file
log "Installing devcadence.md..."
if curl -sf "$REPO_RAW/commands/devcadence.md" -o ".opencode/commands/devcadence.md"; then
  ok "Downloaded"
else
  fail "Failed to download devcadence.md — check your internet connection"
fi

# [7] Verify installation
log "Verifying installation..."
MISSING=0
if [ ! -f ".opencode/skills/devcadence/SKILL.md" ]; then
  indent "✗ SKILL.md missing"
  MISSING=1
fi
if [ ! -f ".opencode/commands/devcadence.md" ]; then
  indent "✗ devcadence.md missing"
  MISSING=1
fi
if [ "$MISSING" -eq 0 ]; then
  ok "All files in place"
fi

# [8] Summary
echo ""
echo "Installation complete."
echo ""
echo "Files installed:"
echo "  .opencode/skills/devcadence/SKILL.md"
echo "  .opencode/commands/devcadence.md"
echo ""

# [9] Next steps
if command -v opencode &>/dev/null; then
  echo "Next step:"
  echo "  opencode"
  echo "  /devcadence setup"
  echo ""
else
  echo "Next step:"
  echo "  1. Open your project in opencode"
  echo "  2. Run: /devcadence setup"
  echo ""
  echo "  (opencode not found in PATH — install it first)"
fi
