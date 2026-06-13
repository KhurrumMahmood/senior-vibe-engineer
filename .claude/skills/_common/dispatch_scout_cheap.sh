#!/usr/bin/env bash
# dispatch_scout_cheap.sh — run a scout brief through the host
# tools.code_agent adapter in --read-only mode against a Haiku-class model.
#
# Usage:
#   dispatch_scout_cheap.sh <brief-template> <output-path> [<key>=<value> ...]
#
# Same calling shape as dispatch_scout.sh; chooses a Haiku-class runtime
# instead of `claude -p`. Use this from skills that declare
# `scout_model: cheap` and whose verify briefs are read-and-classify only
# (no shell, no sub-agents, no browser).
#
# Default model: expedient-haiku (Claude Haiku 4.5 via the team's
# Expedient gateway). Team-shared, billed at Haiku rates.
#
# Override via DISPATCH_SCOUT_MODEL — useful aliases:
#   expedient-haiku    Claude Haiku 4.5 via Expedient (default, team)
#   cerebras           GLM-4.7 via Cerebras free tier (personal-account)
#   expedient-coding   Expedient router → coding-tasks model
# Any alias from the host model registry is accepted when the
# <!-- host-adapter --> tools.code_agent runtime is present.
#
# Environment:
#   DISPATCH_SCOUT_MODEL   override model alias (default: expedient-haiku)
#   DISPATCH_SCOUT_WORKDIR override agent workdir (default: $(pwd))
#
# Exit codes (mirror dispatch_scout.sh):
#   0 — agent exited 0 AND <output-path> exists
#   1 — agent exited 0 but <output-path> was not written
#   2 — agent exited nonzero
#   3 — usage / missing brief / substitution/backend error
#
# Why a separate script? `claude -p` uses the user's claude-code session
# (Sonnet/Opus tier). Read-and-classify scouts don't need that judgment
# tier — Haiku is ~10x cheaper per scout. The `--read-only` flag drops
# bash/spawn_agent/claude_tools, so the cheap model can't hallucinate
# calls to tools that aren't there.

set -euo pipefail

if [[ $# -lt 2 ]]; then
    echo "usage: $0 <brief-template> <output-path> [key=value ...]" >&2
    exit 3
fi

BRIEF="$1"
OUTPUT_PATH="$2"
shift 2

if [[ ! -f "$BRIEF" ]]; then
    echo "dispatch_scout_cheap: brief not found: $BRIEF" >&2
    exit 3
fi

SKILL_COMMON_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUBST="$SKILL_COMMON_DIR/scripts/_subst.py"

if [[ ! -f "$SUBST" ]]; then
    echo "dispatch_scout_cheap: substitution helper missing: $SUBST" >&2
    exit 3
fi

PROJECT_DIR="${DISPATCH_SCOUT_WORKDIR:-$(pwd)}"
MODEL="${DISPATCH_SCOUT_MODEL:-expedient-haiku}"
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"

if [[ ! -x "$VENV_PYTHON" ]]; then
    echo "dispatch_scout_cheap: missing venv python at $VENV_PYTHON" >&2
    exit 3
fi

if ! "$VENV_PYTHON" -c 'import tools.code_agent' >/dev/null 2>&1; then
    echo "dispatch_scout_cheap: host-adapter backend unavailable: requires the host tools.code_agent runtime; see <!-- host-adapter -->." >&2
    echo "dispatch_scout_cheap: orchestrator should fall back to inline scouting; no fake cheap-dispatch fallback is available in this repo." >&2
    exit 3
fi

# Make sure the output directory exists before resolving its absolute
# path — `cd "$(dirname …)"` returns empty when the directory hasn't been
# created yet, which would silently bypass the workdir-containment check
# below.
mkdir -p "$(dirname "$OUTPUT_PATH")"

# Reject output paths outside the workdir up front. Scouts run in
# --read-only mode with workdir containment (commit 168ca3c1), so any
# write_file to a path that resolves outside DISPATCH_SCOUT_WORKDIR will
# fail; the scout then helpfully writes elsewhere and the dispatcher
# returns "did not write" with no clear root cause. Catch it here.
ABS_OUTPUT="$(cd "$(dirname "$OUTPUT_PATH")" 2>/dev/null && pwd)/$(basename "$OUTPUT_PATH")"
ABS_WORKDIR="$(cd "$PROJECT_DIR" && pwd)"
case "$ABS_OUTPUT" in
    "$ABS_WORKDIR"/*) ;;
    *)
        echo "dispatch_scout_cheap: output path outside workdir" >&2
        echo "  output:  $ABS_OUTPUT" >&2
        echo "  workdir: $ABS_WORKDIR" >&2
        echo "  hint: scouts run with --read-only workdir containment; pick an output path under the workdir, or override DISPATCH_SCOUT_WORKDIR." >&2
        exit 3
        ;;
esac

PROMPT_FILE="$(mktemp -t dispatch_scout_cheap.XXXXXX)"
trap 'rm -f "$PROMPT_FILE"' EXIT

python3 "$SUBST" "$BRIEF" "$PROMPT_FILE" "$@" || {
    echo "dispatch_scout_cheap: placeholder substitution failed" >&2
    exit 3
}

set +e
(
    cd "$PROJECT_DIR" && \
    "$VENV_PYTHON" -m tools.code_agent \
        --prompt "$(cat "$PROMPT_FILE")" \
        --workdir "$PROJECT_DIR" \
        --model "$MODEL" \
        --read-only
) \
    > "${OUTPUT_PATH}.stdout" \
    2> "${OUTPUT_PATH}.stderr"
AGENT_RC=$?
set -e

if [[ $AGENT_RC -ne 0 ]]; then
    echo "dispatch_scout_cheap: code_agent exited $AGENT_RC (brief=$BRIEF, model=$MODEL)" >&2
    # Dump both streams: tools/code_agent.py prints structured agent output
    # to stdout and fatal traces to stderr, so the diagnostic the human
    # needs may be in either place depending on how the agent failed.
    if [[ -s "${OUTPUT_PATH}.stdout" ]]; then
        echo "--- last 20 lines of ${OUTPUT_PATH}.stdout ---" >&2
        tail -n 20 "${OUTPUT_PATH}.stdout" >&2
    fi
    if [[ -s "${OUTPUT_PATH}.stderr" ]]; then
        echo "--- last 20 lines of ${OUTPUT_PATH}.stderr ---" >&2
        tail -n 20 "${OUTPUT_PATH}.stderr" >&2
    fi
    exit 2
fi

if [[ ! -f "$OUTPUT_PATH" ]]; then
    echo "dispatch_scout_cheap: scout did not write $OUTPUT_PATH (brief=$BRIEF, model=$MODEL)" >&2
    exit 1
fi

echo "OK $OUTPUT_PATH"
