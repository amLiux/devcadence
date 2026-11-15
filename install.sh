#!/usr/bin/env bash
set -euo pipefail

# DevCadence Installer
# Fetches skill from GitHub and installs into your project.
# Usage: curl -sL https://raw.githubusercontent.com/amLiux/devcadence/main/install.sh | bash

REPO_RAW="https://raw.githubusercontent.com/amLiux/devcadence/main"
STEP=0

# Keep in sync with update.sh MANAGED_SCRIPTS (enforced by tests/test_install.py).
MANAGED_SCRIPTS="tickets.py logs.py progress.py storage.py update.py migrate.py coder.py coder_prompt.md"

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

warn() {
  indent "! $1"
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

# [6] Fetch command file (skip if exists — config lives here)
log "Installing devcadence.md..."
if [ -f ".opencode/commands/devcadence.md" ]; then
  ok "Skipped — already exists (config preserved)"
else
  if curl -sf "$REPO_RAW/commands/devcadence.md" -o ".opencode/commands/devcadence.md"; then
    ok "Downloaded"
  else
    fail "Failed to download devcadence.md — check your internet connection"
  fi
fi

# [7] Fetch scripts (the skill's File Manifest expects scripts/ at project root)
log "Installing scripts/..."
mkdir -p scripts
for script in $MANAGED_SCRIPTS; do
  TEMP_SCRIPT=$(mktemp)
  if curl -sf "$REPO_RAW/scripts/$script" -o "$TEMP_SCRIPT"; then
    if [ -f "scripts/$script" ] && diff -q "$TEMP_SCRIPT" "scripts/$script" >/dev/null 2>&1; then
      ok "scripts/$script up to date"
    else
      cp "$TEMP_SCRIPT" "scripts/$script"
      ok "scripts/$script"
    fi
  else
    rm -f "$TEMP_SCRIPT"
    fail "Failed to download scripts/$script — check your internet connection"
  fi
  rm -f "$TEMP_SCRIPT"
done

# [8] Security context (never overwrite a project's own blueprint)
log "Installing SECURITY.md..."
if [ -f "SECURITY.md" ]; then
  ok "Skipped — already exists (project security context preserved)"
else
  if curl -sf "$REPO_RAW/SECURITY.md" -o "SECURITY.md"; then
    ok "Downloaded — fill in the blueprint in section 4"
  else
    warn "Could not download SECURITY.md; author one before handling secrets or auth code"
  fi
fi

# [9] Verify installation
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
for script in $MANAGED_SCRIPTS; do
  if [ ! -f "scripts/$script" ]; then
    indent "✗ scripts/$script missing"
    MISSING=1
  fi
done
if [ "$MISSING" -eq 0 ]; then
  ok "All files in place"
else
  fail "Installation incomplete — re-run install.sh"
fi

# [10] Summary
echo ""
echo "Installation complete."
echo ""
echo "Files installed:"
echo "  .opencode/skills/devcadence/SKILL.md"
echo "  .opencode/commands/devcadence.md"
for script in $MANAGED_SCRIPTS; do
  echo "  scripts/$script"
done
echo "  SECURITY.md"
echo ""

# [11] Next steps
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
