#!/usr/bin/env bash
# Apply MCP server registry → user-scope ~/.claude.json mcpServers
# Idempotent: skip unchanged, update if spec differs, warn on orphans.
# Called by /git-routine pull (auto), or directly for manual sync.
set -euo pipefail

REGISTRY="$HOME/.claude/skills/_mcp-servers/registry.json"
CLAUDE_CONFIG="$HOME/.claude.json"

if [ ! -r "$REGISTRY" ]; then
  echo "  ✗ registry.json not found: $REGISTRY" >&2
  exit 1
fi

# Target servers (from registry — git-tracked single source of truth)
target_names=$(jq -r '.mcpServers | keys[]' "$REGISTRY")

# Current user-scope servers (top-level mcpServers in ~/.claude.json)
current_names=$(jq -r '.mcpServers // {} | keys[]' "$CLAUDE_CONFIG" 2>/dev/null || true)

added=0; updated=0; unchanged=0; orphan=0

# Add or update
for name in $target_names; do
  target_spec=$(jq -c ".mcpServers[\"$name\"]" "$REGISTRY")
  if echo "$current_names" | grep -qx "$name"; then
    current_spec=$(jq -c ".mcpServers[\"$name\"]" "$CLAUDE_CONFIG")
    if [ "$target_spec" = "$current_spec" ]; then
      echo "  = unchanged: $name"
      unchanged=$((unchanged+1))
    else
      claude mcp remove "$name" >/dev/null 2>&1 || true
      claude mcp add-json --scope user "$name" "$target_spec" >/dev/null
      echo "  ↻ updated:   $name"
      updated=$((updated+1))
    fi
  else
    claude mcp add-json --scope user "$name" "$target_spec" >/dev/null
    echo "  ✓ added:     $name"
    added=$((added+1))
  fi
done

# Orphans (in user config but not in registry) — warn only, do not auto-remove
for name in $current_names; do
  # Skip claude.ai connectors (managed by Anthropic OAuth, not user-registered)
  [[ "$name" =~ ^claude\.ai ]] && continue
  if ! echo "$target_names" | grep -qx "$name"; then
    echo "  ⚠ orphan:    $name (in user config but not in registry — manual remove via 'claude mcp remove $name')"
    orphan=$((orphan+1))
  fi
done

echo
echo "  Summary: +$added added, ↻$updated updated, =$unchanged unchanged, ⚠$orphan orphan"
