#!/usr/bin/env bash
set -euo pipefail

# DevCadence Updater
# Pulls latest files from GitHub, preserves your config.
# Usage: curl -sL https://raw.githubusercontent.com/amLiux/devcadence/main/update.sh | bash

REPO_RAW="https://raw.githubusercontent.com/amLiux/devcadence/main"
STEP=0
CHANGES=0

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

changed() {
  indent "→ $1"
  CHANGES=$((CHANGES + 1))
}

fail() {
  indent "✗ $1"
  exit 1
}

backup_config() {
  local file="$1"
  if [ ! -f "$file" ]; then
    return
  fi
  # Extract everything from "# Project Config" to end of file
  sed -n '/^# Project Config$/,$p' "$file" 2>/dev/null || true
}

echo ""
echo "DevCadence Updater"
echo "==================="
echo "Target:  $(pwd)"
echo ""

# [1] Check .opencode exists
log "Checking installation..."
if [ ! -d ".opencode/skills/devcadence" ]; then
  fail "DevCadence not installed. Run install.sh first."
fi
ok "Found"

# [2] Update SKILL.md
log "Updating SKILL.md..."
TEMP_SKILL=$(mktemp)
if curl -sf "$REPO_RAW/skills/devcadence/SKILL.md" -o "$TEMP_SKILL"; then
  if diff -q "$TEMP_SKILL" ".opencode/skills/devcadence/SKILL.md" >/dev/null 2>&1; then
    ok "Up to date"
  else
    changed "Updated"
    diff --color=auto ".opencode/skills/devcadence/SKILL.md" "$TEMP_SKILL" 2>/dev/null || true
    cp "$TEMP_SKILL" ".opencode/skills/devcadence/SKILL.md"
  fi
else
  fail "Failed to download SKILL.md"
fi
rm -f "$TEMP_SKILL"

# [3] Update command file (preserve config block)
log "Updating devcadence.md..."
TEMP_CMD=$(mktemp)
if curl -sf "$REPO_RAW/commands/devcadence.md" -o "$TEMP_CMD"; then
  CONFIG_BLOCK=$(backup_config ".opencode/commands/devcadence.md")
  if [ -n "$CONFIG_BLOCK" ]; then
    # Remove old config block from downloaded file, append local config
    sed -i.bak '/^# Project Config$/,$d' "$TEMP_CMD" 2>/dev/null || sed '/^# Project Config$/,$d' "$TEMP_CMD" > "$TEMP_CMD.tmp" && mv "$TEMP_CMD.tmp" "$TEMP_CMD" 2>/dev/null || true
    echo "" >> "$TEMP_CMD"
    echo "$CONFIG_BLOCK" >> "$TEMP_CMD"
  fi
  if diff -q "$TEMP_CMD" ".opencode/commands/devcadence.md" >/dev/null 2>&1; then
    ok "Up to date"
  else
    changed "Updated (config preserved)"
    diff --color=auto ".opencode/commands/devcadence.md" "$TEMP_CMD" 2>/dev/null || true
    cp "$TEMP_CMD" ".opencode/commands/devcadence.md"
  fi
else
  fail "Failed to download devcadence.md"
fi
rm -f "$TEMP_CMD" "$TEMP_CMD.tmp" "$TEMP_CMD.bak"

# [4] Update scripts/
log "Updating scripts..."
mkdir -p scripts
for script in tickets.py logs.py progress.py; do
  TEMP_SCRIPT=$(mktemp)
  if curl -sf "$REPO_RAW/scripts/$script" -o "$TEMP_SCRIPT" 2>/dev/null; then
    if [ -f "scripts/$script" ] && diff -q "$TEMP_SCRIPT" "scripts/$script" >/dev/null 2>&1; then
      ok "scripts/$script up to date"
    else
      changed "scripts/$script"
      cp "$TEMP_SCRIPT" "scripts/$script"
    fi
  else
    indent "scripts/$script not found upstream (skip)"
  fi
  rm -f "$TEMP_SCRIPT"
done

# [5] Summary
echo ""
if [ "$CHANGES" -eq 0 ]; then
  echo "Everything up to date. No changes."
else
  echo "Updated $CHANGES file(s)."
fi
echo ""

# [6] Version hint
if command -v opencode &>/dev/null; then
  echo "Next step:"
  echo "  /devcadence standup"
  echo ""
else
  echo "Next step:"
  echo "  Open your project in opencode"
  echo "  Run: /devcadence standup"
  echo ""
fi
