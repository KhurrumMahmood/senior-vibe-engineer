#!/usr/bin/env bash
# dispatch_scout.sh — run a scout brief as a `claude -p` subprocess.
#
# Usage:
#   dispatch_scout.sh <brief-template> <output-path> [<key>=<value> ...]
#
# Reads the brief template, substitutes {{key}} placeholders with the given
# values (via scripts/_subst.py — handles multi-line values correctly),
# invokes `claude -p --dangerously-skip-permissions` with the expanded
# prompt from a neutral cwd, and exits 0 only if the scout actually wrote
# to <output-path>.
#
# Why subprocess dispatch? The `Agent` tool works only one level deep — if
# a skill is itself invoked as a sub-agent, Agent is unavailable and the
# skill silently falls back to inline work. `claude -p` spawns a brand-new
# Claude Code process with the full tool set, so the fan-out layer is
# nesting-depth-agnostic. Cost: ~4-8s process-spawn + full context reload
# per scout, vs the Agent tool's ~0s overhead. Use this when the skill
# needs to compose cleanly; use Agent for shallow top-level scans.
#
# Log files land next to the output:
#   <output-path>.stdout   (claude's text response)
#   <output-path>.stderr   (spawn errors, timeouts)
#
# Exit codes:
#   0 — claude exited 0 AND <output-path> exists
#   1 — claude exited 0 but <output-path> was not written (scout failed
#       its contract)
#   2 — claude exited nonzero
#   3 — usage / missing brief / substitution error

set -euo pipefail

if [[ $# -lt 2 ]]; then
    echo "usage: $0 <brief-template> <output-path> [key=value ...]" >&2
    exit 3
fi

BRIEF="$1"
OUTPUT_PATH="$2"
shift 2

if [[ ! -f "$BRIEF" ]]; then
    echo "dispatch_scout: brief not found: $BRIEF" >&2
    exit 3
fi

SKILL_COMMON_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUBST="$SKILL_COMMON_DIR/scripts/_subst.py"

if [[ ! -f "$SUBST" ]]; then
    echo "dispatch_scout: substitution helper missing: $SUBST" >&2
    exit 3
fi

# Build a prompt tempfile with placeholders substituted.
PROMPT_FILE="$(mktemp -t dispatch_scout.XXXXXX)"
trap 'rm -f "$PROMPT_FILE"' EXIT

python3 "$SUBST" "$BRIEF" "$PROMPT_FILE" "$@" || {
    echo "dispatch_scout: placeholder substitution failed" >&2
    exit 3
}

# Ensure output directory exists (the scout may not create it itself).
mkdir -p "$(dirname "$OUTPUT_PATH")"

# Spawn the scout from /private/tmp so Claude does not implicitly auto-load
# project context from cwd. Repo access is granted deliberately with --add-dir.
# The `--` separator is required because --add-dir accepts multiple paths.
# --dangerously-skip-permissions because scouts are read-only leaves and
# interactive prompts would block parallel runs.
# --output-format text because scouts write files, not JSON-to-stdout.
PROJECT_DIR="$(pwd)"
CLAUDE_WORKDIR="${CLAUDE_SCOUT_WORKDIR:-/private/tmp}"
mkdir -p "$CLAUDE_WORKDIR"

set +e
(
    cd "$CLAUDE_WORKDIR" && \
    claude -p \
        --dangerously-skip-permissions \
        --output-format text \
        --add-dir "$PROJECT_DIR" \
        -- "$(cat "$PROMPT_FILE")"
) \
    > "${OUTPUT_PATH}.stdout" \
    2> "${OUTPUT_PATH}.stderr"
CLAUDE_RC=$?
set -e

if [[ $CLAUDE_RC -ne 0 ]]; then
    echo "dispatch_scout: claude -p exited $CLAUDE_RC (brief=$BRIEF)" >&2
    exit 2
fi

if [[ ! -f "$OUTPUT_PATH" ]]; then
    echo "dispatch_scout: scout did not write $OUTPUT_PATH (brief=$BRIEF)" >&2
    exit 1
fi

echo "OK $OUTPUT_PATH"
