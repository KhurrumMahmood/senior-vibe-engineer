# `.claude/skill-use/` — fifth-tier lesson capture (skill effectiveness)

Records *which skill was invoked, on what, with what outcome, and what
the human overrode*. Feeds future skill-split decisions empirically —
when `/propose-boundary` runs on a skill directory, it can read this
surface as an evidence channel alongside naming alignment and call-edge
density.

## Why a fifth tier

The four existing lesson-capture tiers each have a distinct role
(host-project root-agent guide lists them):

| Tier | Surface | Role |
|---|---|---|
| 1 | `.claude/tasks/lessons.md` | Diary — repeated/non-obvious code fixes |
| 2 | `.claude/docs/known-issues.md` | Current-state operational gotchas |
| 3 | `.claude/docs/precedents.yml` | Updateable implementation case law |
| 4 | `ai-docs/decisions/` | ADRs — choices that constrain future work |

None of them captures *skill effectiveness*. Mixing skill-ROI signal
into any of the four would dilute their role. A fifth tier with a
clear single purpose is cleaner.

## Files

- `log.jsonl` — append-only event log. Gitignored by default (privacy:
  target paths + human-override strings may leak project context).
- `archive/log-<TS>.jsonl.gz` — periodic gzipped snapshots written by
  `compact.py`. Gitignored.
- `lessons-<TS>.md` — distilled per-window digest written by
  `compact.py`. The primary reading surface. Not gitignored by default —
  the digest is summarized and safe to commit.
- `project.py` — projection helper; reads `log.jsonl` and emits a
  per-skill summary to `reports/skill-use/projection-<TS>.md`.
- `compact.py` — manual archive + digest script. Reads `log.jsonl`,
  writes `lessons-<TS>.md`, gzips the log into `archive/`, truncates
  `log.jsonl` to a sentinel header pointing at the latest digest.

## Event schema

One JSON object per line. Required fields:

```json
{
  "ts": "2026-05-14T10:32:00Z",
  "skill": "find-omnibus",
  "event_kind": "skill_run",
  "target": "<path or identifier>",
  "artifact": "reports/find-omnibus/scan-20260514-1032/findings.json",
  "outcome": "useful",
  "human_override": null,
  "duration_s": 47,
  "follow_up_skill": "refactor-subsystem"
}
```

Field meanings:

- `ts` — ISO-8601 UTC timestamp when the skill terminated.
- `skill` — the slug from the skill's frontmatter `name:` field
  (without the leading `/`).
- `event_kind` — optional; existing events without the field are
  treated as `skill_run`. `/which-shape` emits `recommendation`
  events, which projections summarize separately so routing advice
  does not pollute skill useful-rate metrics.
- `target` — the path or identifier the skill was invoked on.
  May be a file path, subsystem slug, scan id, or a skill directory.
- `artifact` — relative path to the primary artifact produced. `null`
  if the skill produced no file artifact.
- `outcome` — one of `useful` | `partial` | `noop` | `overridden`.
  `useful`: produced a finding/proposal the human acted on without
  significant rework.
  `partial`: produced something but the human had to fill substantial
  gaps.
  `noop`: produced no actionable finding (clean target, or skill mis-
  applied — `human_override` clarifies which).
  `overridden`: produced something the human rejected; `human_override`
  records the reason.
- `human_override` — one-line string; required when `outcome != useful`,
  `null` otherwise. Short, structured: "scope-too-broad",
  "wrong-target-kind", "false-positive: <pattern>",
  "missed-cluster: <cluster>".
- `duration_s` — wall-clock seconds the skill ran (helper script time,
  not orchestrator time).
- `follow_up_skill` — the next skill the human invoked (or `null` if
  none). Captures composition patterns.

Shape recommendation events add these optional fields:

```json
{
  "event_kind": "recommendation",
  "skill": "which-shape",
  "shape": "legacy-stabilization",
  "confidence": "high",
  "project_context_state": "missing",
  "recommended_first_skill": "/map-subsystem"
}
```

Use `outcome: "overridden"` plus a short `human_override` stem such as
`wrong-shape`, `too-much-process`, `missed-project-intake`, or
`should-have-guarded` when the recommendation was wrong.

## Opt-in capture

Each skill author adds a one-liner at the skill's terminal stage that
appends an event to `log.jsonl` via the shared helper. No retroactive
instrumentation is required; instrumentation lands as we touch each
skill.

The opt-in line (Python helper):

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_common"))
from skill_use import log_event  # noqa: E402

# ... at the skill's terminal stage ...
log_event(
    skill="<skill-name>",
    target="<target>",
    artifact="<artifact-path-or-None>",
    elapsed_s=time.monotonic() - start,
)
```

The helper lives at `.claude/skills/_common/skill_use.py`. It locates
the repo root via a `.claude/` walk-up, so callers don't need to track
`parents[N]` depth in the helper itself — pick the `sys.path.insert`
depth that points at `_common/` from your script's location (the
example above is correct for scripts at
`.claude/skills/<skill>/scripts/<file>.py`). Failures are swallowed
by design — telemetry must never block the skill from terminating.

For shell-based skills, the equivalent shell append:

```bash
printf '%s\n' '{"ts":"'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'","skill":"<name>",...}' \
  >> "$REPO_ROOT/.claude/skill-use/log.jsonl"
```

## Projection workflow

Run `python3 .claude/skill-use/project.py` to emit
`reports/skill-use/projection-<TS>.md` with per-skill stats:

- Invocation count (`n=`)
- `useful` rate (% of invocations where `outcome == "useful"`)
- Common `human_override` reasons (clustered by stem)
- Avg `duration_s`
- Most common `follow_up_skill`

Output is for human review. No auto-decisioning — projection is
*evidence*, not *verdict*. Under-sampled rows (`n` low) are visible so
their stats don't get over-weighted.

## Compaction workflow

Run `python3 .claude/skill-use/compact.py` periodically (no automatic
trigger in v1; cadence emerges from manual use). The script:

1. Reads the current `log.jsonl`.
2. Distills events into `lessons-<TS>.md`:
   - Per-skill `useful` rate over the window
   - Recurring `human_override` themes (cluster by stem)
   - Notable composition patterns (skill A → skill B handoffs)
   - Calibration triggers (e.g. "skill X overridden rate ≥ 40% across
     n=N — boundary-split candidate; invoke `/propose-boundary
     .claude/skills/X/`").
3. Gzips the raw log to `archive/log-<TS>.jsonl.gz` (never deleted).
4. Truncates `log.jsonl` to a sentinel header line pointing at the
   latest digest + archive.

This keeps the active log small while preserving the raw stream
forever. The digest becomes the primary reading surface; the archive
holds the receipts.

A future `/compact-skill-log` skill will formalize the workflow once
the manual flow has been exercised a few times.

## Gitignore guidance for adopters

Add to your project's `.gitignore`:

```
.claude/skill-use/log.jsonl
.claude/skill-use/archive/log-*.jsonl.gz
```

The `lessons-*.md` digest is summarized and safe to commit by default.

## Privacy note

`target` and `human_override` may contain repo-local paths, identifier
names, or short freeform reasons. Default to gitignore; opt in to
commit only if the project's repo policy allows.

## Connection to boundary work

Once the log accumulates ~20 events per skill, `/propose-boundary`
invoked on a skill directory can consume that skill's projection as a
seam-evidence channel. A 40% `overridden` rate at one phase of a
multi-phase skill is a missing-boundary signal — the same shape as the
call-edge-density signal, sourced from outcome data instead of code.
