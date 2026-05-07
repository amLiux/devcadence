#!/usr/bin/env bash
set -euo pipefail

echo "Installing DevCadence skill..."

# Detect opencode
if command -v opencode &>/dev/null; then
  TARGET="$HOME/.config/opencode/skills/devcadence"
  mkdir -p "$TARGET"
  cp skills/devcadence/SKILL.md "$TARGET/SKILL.md"
  echo "  ✅ opencode: installed to $TARGET"
fi

# Detect other agents (cursor, claude, etc.)
if [ -d "$HOME/.cursor/rules" ]; then
  mkdir -p "$HOME/.cursor/rules"
  cp skills/devcadence/SKILL.md "$HOME/.cursor/rules/devcadence.mdc"
  echo "  ✅ cursor: installed"
fi

echo ""
echo "Done. Type /devcadence to start."
