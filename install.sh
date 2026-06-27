#!/usr/bin/env bash
# Installs dependencies and prints the exact config for Claude Code and
# Claude Desktop, with absolute paths resolved for THIS machine.
# Re-run this on each PC after cloning.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"
OUT_DIR="${IMAGE_OUTPUT_DIR:-$HOME/gpt-image-output}"
mkdir -p "$OUT_DIR"

if command -v uv >/dev/null 2>&1; then
  echo "==> Installing dependencies with uv"
  uv sync
  CMD_BIN="$(command -v uv)"
  CMD_ARGS=(run --directory "$REPO_DIR" gpt-image-mcp)
else
  echo "==> uv not found; creating a virtualenv with pip instead"
  python3 -m venv .venv
  ./.venv/bin/pip install --quiet --upgrade pip
  ./.venv/bin/pip install --quiet -e .
  CMD_BIN="$REPO_DIR/.venv/bin/gpt-image-mcp"
  CMD_ARGS=()
fi

# Build a JSON array of args
args_json="[]"
if [ "${#CMD_ARGS[@]}" -gt 0 ]; then
  args_json="["
  for i in "${!CMD_ARGS[@]}"; do
    [ "$i" -gt 0 ] && args_json+=", "
    args_json+="\"${CMD_ARGS[$i]}\""
  done
  args_json+="]"
fi

# Build the `claude mcp add` command
cc_cmd="claude mcp add gpt-image --scope user -e OPENAI_API_KEY=\$OPENAI_API_KEY -e IMAGE_OUTPUT_DIR=\"$OUT_DIR\" -- \"$CMD_BIN\""
for a in "${CMD_ARGS[@]:-}"; do
  [ -n "$a" ] && cc_cmd+=" \"$a\""
done

cat <<MSG

============================================================
 Install complete.
============================================================

1) CLAUDE CODE — make sure OPENAI_API_KEY is exported in your shell, then run:

$cc_cmd

   Verify with:  claude mcp list      (and /mcp inside a session)

2) CLAUDE DESKTOP — add this block under "mcpServers" in your config file,
   replace sk-REPLACE_ME with your key, then fully quit & relaunch Desktop:

    "gpt-image": {
      "command": "$CMD_BIN",
      "args": $args_json,
      "env": {
        "OPENAI_API_KEY": "sk-REPLACE_ME",
        "IMAGE_OUTPUT_DIR": "$OUT_DIR"
      }
    }

   Config file:
     macOS:   ~/Library/Application Support/Claude/claude_desktop_config.json
     Windows: %APPDATA%\\Claude\\claude_desktop_config.json
     Open it via Desktop: Settings > Developer > Edit Config

Images will be saved to: $OUT_DIR
============================================================
MSG
