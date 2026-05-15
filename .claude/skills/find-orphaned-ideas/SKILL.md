---
name: find-orphaned-ideas
description: Detect ideas that need attention but are not getting it. Seven modes — stale (in-flight, no event in N days), harvest (has-more-potential, not in-flight), plan-dropouts (in a plan file but missing from ledger), todo (TODO/FIXME orphans in source files), stale-plans (proposed plans > N days silent with no ledger intake), dead-prototype (orphan routes/templates from a /find-dormant report), attention-gap (importance-weighted audit per ADR 0016, reads `.claude/docs/importance-map.md`). Read-only audit by default; can optionally write `stalled` transition events when --apply-stale is set. Read .claude/docs/idea-ledger.md when authoring or debugging this skill, `.claude/docs/todo-tuning.md` when calibrating --todo, and `.claude/docs/importance-map.md` (plus ADR 0016) when calibrating --attention-gap.
argument-hint: "[--stale | --harvest | --plan-dropouts <path> | --todo | --stale-plans | --dead-prototype | --attention-gap | --all] [--from-report <path>] [--stale-days N] [--stale-plans-days N] [--min-age-days N] [--min-words N] [--apply-stale]"
allowed-tools: Bash, Read, Edit
user-invocable: true
tier: maintenance
job: suspect
best_for: |
  Weekly / on-demand audit of the idea ledger to catch:
  - in-flight ideas that have gone silent (stale detection)
  - harvested ideas with explicit remaining capacity that nobody picked
    back up (harvest opportunities)
  - plan or backlog items that should have a ledger entry but don't
    (plan-ledger drift)
  Pair with `/track-idea event` to act on findings.
not_for: |
  Capturing new ideas (use /track-idea intake).
  Adding lessons or transitions (use /track-idea event).
  Promoting to the pattern library (use /promote-idea-to-pattern).
  Bulk import from history (use /extract-existing-ideas).
  Detecting drift in the pattern library (that's audit-pattern-library;
  a future skill).
escalate_to: |
  /track-idea event when a finding needs an explicit transition or
  marker change. /extract-existing-ideas when the plan-dropouts list
  reveals a systemic gap (many items missing) that warrants a backfill.
language: any
framework: any
---

# /find-orphaned-ideas

You are the **read-side audit** for the Tier 1 idea ledger. You surface
ideas the user might have lost track of and, in optional write mode,
emit stalled-transition events on the user's behalf.

You do NOT capture new ideas — that's `/track-idea intake`. You do NOT
modify intake records — append events through `/track-idea event`. You
do NOT prune the ledger — the ledger is append-only forever.

The schema, projection rules, and full skill-↔-ledger interaction table
live in `.claude/docs/idea-ledger.md`. **Read that file** before
reasoning about a non-trivial finding.

## Core beliefs

1. **Detection ≠ action.** The default mode is read-only. Findings are
   surfaced; the user decides whether to act. `--apply-stale` is the
   single exception, and it carries an audit trail (a `transition` event
   per applied finding).
2. **Seven orthogonal signals.** Stale, harvest, plan-dropout, TODO,
   stale-plans, dead-prototype, and attention-gap capture different
   failure modes — in-flight silence, hidden value, ledger-plan drift,
   source-tree forgetfulness, planning-tree forgetfulness, surface-tree
   forgetfulness, and importance-weighted neglect. Don't conflate;
   report each separately.
3. **`stale_days` is a knob, not a law.** 14 days is the default; some
   projects want shorter, some longer. Surface the threshold in the
   report so the reader can recalibrate.
4. **Plan-dropouts are heuristic.** The matcher does loose token
   equality between plan items and intake ids/titles. Surface the
   matches it found AND the items it dropped so the user can correct
   false positives.

## Argument parsing

Nine forms. `--all` is the default when no mode flag is given.
`--all` covers the three ledger-native modes (Stale, Harvest); the
multi-source modes (Form F–I) are opt-in because their cost profiles
differ (filesystem walks, git subprocess calls, upstream report
dependency, declarative-config dependency).

### Form A — Stale

```
/find-orphaned-ideas --stale [--stale-days N] [--apply-stale]
```

Find every in-flight idea whose `last_event_at` is older than `N` days
(default 14). When `--apply-stale` is set, append a `transition` event
moving each found idea to `stalled`, with summary "auto-detected stale
after N days of inactivity."

### Form B — Harvest

```
/find-orphaned-ideas --harvest
```

Find every idea carrying the `has-more-potential` marker whose state is
NOT `in-flight`. These are the explicit "we left value on the table"
signals.

### Form C — Plan-dropouts

```
/find-orphaned-ideas --plan-dropouts <path>
```

Read a plan/backlog file at `<path>`, extract bullet-list items and
heading-style work items, and report items that have no matching ledger
intake. Match is loose token-equality on slug-normalized titles.

Recommended sources:
- `reports/BACKLOG.md`
- `plans/<slug>.md`
- `ai-docs/specs/<slug>.md`

### Form D — All

```
/find-orphaned-ideas [--all]
```

Run modes A and B together (omitting C, since it needs a path, and F/G/H/I,
which have heavier cost profiles or external dependencies). When the
report has any findings, suggest reads for the user.

### Form E — JSON output

Any form accepts `--json` for machine-readable output. Default is
human-friendly Markdown.

### Form F — TODO/FIXME orphans (multi-source)

```
/find-orphaned-ideas --todo [--min-words N] [--min-age-days N]
```

Walk the source tree for `# TODO:` / `# FIXME:` (Python style) and
`// TODO:` / `// FIXME:` (JS/TS style). Defaults are deliberately
over-surface:

- `min_words = 4` — drops trivial `// TODO` and `# TODO: x` markers but
  keeps anything substantive. Override per-run with `--min-words N`, or
  globally in `.claude/docs/todo-tuning.md`.
- No upper age bound — old TODOs are the most interesting orphans. Opt
  into a lower bound with `--min-age-days N` (uses git mtime of the
  enclosing file as a coarse proxy).
- No automatic test-file skip — test scaffolding often holds the richest
  TODOs. Add path globs to `.claude/docs/todo-tuning.md` under
  `## Path skip` to filter project-specific noise (vendor JS, agent
  worktrees, generated migrations).

Output is per-line: `\`file:line\` [TODO|FIXME] — <body>`. Dedup
against the ledger happens at the `brainstorm.py` hand-off (same gate
as `/extract-existing-ideas`), so re-running is idempotent.

### Form G — Stale plans (multi-source)

```
/find-orphaned-ideas --stale-plans [--stale-plans-days N]
```

Walk `ai-docs/plans/*.md`. Read each plan's status from YAML
front-matter or the first `**Status:**` line. Flag plans whose status
is `proposed`, whose git mtime is older than `N` days (default 30),
and whose stem-slug has no corresponding ledger intake.

Output names the plan path and how long it has been silent. Slug
match is exact (`plan-name.md` → slug `plan-name`); fuzzy matching is
intentionally not done here — the cost of a false negative
("hey, this might already be in the ledger") is lower than the cost
of a false positive that misleads the user into reconfiguring an
existing intake.

### Form H — Dead-prototype (multi-source)

```
/find-orphaned-ideas --dead-prototype [--from-report <path>]
```

Consume a `/find-dormant` (or `/find-dead-route-surface`) report. Two
ways to supply the report:

- Explicit: `--from-report path/to/report.json`.
- Auto-resolve: if `--from-report` is omitted, the script picks the
  most recently-modified `reports/find-dormant/scan-*/` directory and
  reads the first `*.json` inside.

If neither path is available, the script exits 2 with a real
diagnostic (it does NOT silently say "run it first"). This mode is
downstream of `/find-dormant`'s output schema — a schema change there
is breaking. The reader tolerates top-level lists or objects with one
of: `items`, `findings`, `dormant`, `results`, `candidates`. Per
entry, it reads `path` / `file` / `route` / `template` and
`reason` / `description` / `kind`.

### Form I — Attention-gap (importance-weighted audit)

```
/find-orphaned-ideas --attention-gap
```

Read the declarative importance map at `.claude/docs/importance-map.md`
(shape defined by ADR 0016), rank declared areas by tier
(`critical` > `core` > `supporting`), and emit a report row per area
listing its locators and any drift.

**Skeleton scope (v1).** The skeleton ships the graceful-degradation
contract and a rendered table with locator counts. The full design —
signal joins (TODO density inside each area, days-since-last-event for
ledger ideas mapped to each area, harvest opportunities inside each
area), output columns, and the "useful audit" threshold — is deferred
to a post-ADR addendum.

**Default-absent.** If the map file does not exist or is empty, the
mode emits "No importance map declared — see ADR 0016" and exits
cleanly. This is the contract from ADR 0016 ("Default when absent:
emit notice, exit clean"); the alternative (silent frequency fallback)
was rejected because it would falsely imply a weighted audit.

**Default-malformed.** If the map has no parseable areas, the mode
emits a diagnostic naming the expected shape (Tier + Locators) and
exits cleanly — no crash.

**Drift detector.** For every locator line, the skeleton flags
`path:<glob>` entries whose path does not exist on disk and
`kind:<subsystem_kind>` entries that do not appear in the ledger's
projected `subsystem_kind` set. Drift is reported in a dedicated
sub-section under the area list; it does NOT suppress the area itself.

Locator shapes (ADR 0016 §File shape):
- `path:<folder-or-glob>` — matches the filesystem; globs allowed.
- `kind:<subsystem_kind>` — matches a ledger projection's
  `subsystem_kind`. `subsystem_kind` is the canonical taxonomy in
  `.claude/docs/idea-ledger.md`.

## Pipeline

### Stage 0 — Setup

**Pre:** argument parsed. **Post:** ledger path resolved.

The ledger lives at `.claude/ideas/log.jsonl`. If the file doesn't
exist or is empty, exit 0 with a message — there is nothing to detect.

### Stage 1 — Run the detectors

**Pre:** ledger loaded. **Post:** raw findings per mode.

```bash
python3 .claude/skills/find-orphaned-ideas/scripts/find.py \
  [--stale | --harvest | --plan-dropouts <path> \
   | --todo | --stale-plans | --dead-prototype \
   | --attention-gap | --all] \
  [--stale-days N] [--stale-plans-days N] \
  [--min-words N] [--min-age-days N] \
  [--from-report <path>] [--apply-stale] [--json]
```

The script reads the ledger via `ideas_lib.load_ledger` and calls
`find_stalled`, `find_harvest_opportunities`, and `find_plan_dropouts`
for the ledger-native modes. The multi-source modes (todo, stale-plans,
dead-prototype) walk the filesystem and shell out to `git log` for
mtime; they share the ledger projection only for the dedup cross-check
in `--stale-plans`. Detectors are deterministic; the harness fixtures
at `.claude/tests/ideas/fixtures/` cover the ledger-native cases.

### Stage 2 — Render the report

**Pre:** findings collected. **Post:** human-readable summary delivered.

The default render is Markdown. Shape:

```
# Orphaned-idea audit (now: <iso>, stale_days: N)

## Stale (in-flight > N days)
- <id> — <title>
  (last event: <iso>, days silent: D)
  ...

## Harvest opportunities (has-more-potential, not in-flight)
- <id> — <title> [state]
  (markers: <list>)
  ...

## Plan-dropouts (in <plan-path>, missing from ledger)
- <item line>
- ...

## Suggested next actions
- For stale findings: review and either resume work or
  `/track-idea event <id> --kind transition --to-state done
  --outcome deferred`
- For harvest opportunities: review with intent to resume, or
  `/track-idea event <id> --kind marker --markers-removed has-more-potential`
- For plan-dropouts: backfill with `/track-idea intake <slug>`
- For TODO/FIXME orphans: review each, then either resolve in code,
  remove the comment, or hand the survivors to
  `/extract-existing-ideas` (which calls `/brainstorm-ideas` for
  dedup + validation)
- For stale-plans: either resume the plan, mark it `done outcome=deferred`
  inline, or backfill with `/track-idea intake <slug>`
- For dead-prototype: act through `/fix-workflow` against the
  upstream `/find-dormant` cluster, or backfill an intake for the
  decision (delete vs. revive)
- For attention-gap: open the named importance area, walk the
  locators, decide whether ledger / TODO / plan activity in that
  area matches its declared tier. Drift findings → update the map
  file (rename or remove the stale locator).
```

Sections with zero findings show "(none)" rather than being omitted —
this confirms the detector ran.

### Stage 3 — Optional write (--apply-stale)

**Pre:** Form A active AND `--apply-stale` flag set AND findings exist.
**Post:** one `transition` event appended per finding.

The script handles the write through `ideas_lib.append_record`. Each
appended event has:

- `event_kind: transition`
- `from_state: in-flight`
- `to_state: stalled`
- `summary: "auto-detected stale after <N> days of inactivity"`

After write, re-run Stage 1 and report the now-updated state. The user
should see "0 stale findings" on the second pass (sanity check).

### Stage 4 — Effectiveness log

**Pre:** report delivered. **Post:** one line appended to
`reports/_meta/effectiveness.jsonl`.

```bash
python3 scripts/log_effectiveness.py \
  --skill find-orphaned-ideas \
  --scan-id "audit-$(date +%s)" \
  --target ".claude/ideas/log.jsonl" \
  --findings-total $TOTAL \
  --buckets "{\"stale\": ${N_STALE}, \"harvest\": ${N_HARVEST}, \"plan_dropouts\": ${N_DROPOUTS}, \"todo\": ${N_TODO}, \"stale_plans\": ${N_STALE_PLANS}, \"dead_prototype\": ${N_DEAD_PROTOTYPE}, \"attention_gap_areas\": ${N_ATTENTION_AREAS}}"
```

### Stage 5 — Stop

Do not auto-act on findings except via `--apply-stale`. The detector is
advisory; the user invokes `/track-idea event` for the rest.

## Non-goals

- Modifying intake records (events are the write surface).
- Pruning the ledger (it's append-only forever).
- Promoting to the pattern library (`/promote-idea-to-pattern`).
- Bulk import from history (`/extract-existing-ideas`).
- Detecting *pattern* library drift (a future `/audit-pattern-library`
  will own that).
- Inferring whether a stale idea should be `done outcome=deferred` vs
  reopened — surface the finding and let the user judge.

## When things go sideways

| Symptom | Action |
|---|---|
| Ledger file missing or empty | Exit 0 with "no ledger yet" |
| `--plan-dropouts` path doesn't exist | Exit 2 with usage error |
| Plan file has no extractable items (no bullets, no headings) | Report "(no items extracted; check format)" and continue with other modes |
| `--apply-stale` would write but no stale findings | No-op, report success |
| `--apply-stale` write fails mid-batch | Stop at the failing record; report what was written and what was not (the ledger remains valid) |
| Same idea matches multiple modes (e.g. stale AND harvest) | Report under each section; do not deduplicate |
| `--todo` against binary or non-UTF8 file | Skip silently; the file walk continues |
| `--todo` produces project-specific noise (vendor JS, worktrees) | Add globs to `.claude/docs/todo-tuning.md` `## Path skip` |
| `--todo` git mtime lookup fails (not a git repo, or file untracked) | The `--min-age-days` filter drops that file; without the filter the TODO still surfaces |
| `--stale-plans` plan with no parseable status | Skipped (status defaults to None, which is not `proposed`) |
| `--stale-plans` plan slug collides with an existing ledger intake | Skipped — the cross-check is exact stem-slug match |
| `--dead-prototype` with no path AND no `reports/find-dormant/` scans | Exit 2 with usage error naming both options |
| `--dead-prototype` report exists but JSON has no recognized array key | Exit 2 with the list of accepted keys |
| Same path matches multiple new modes (e.g. TODO in a stale plan file) | Report under each section; do not deduplicate |
| `--attention-gap` with no `.claude/docs/importance-map.md` | Emit "No importance map declared — see ADR 0016" notice; exit 0 |
| `--attention-gap` with an empty or all-prose importance-map.md | Treated as malformed; diagnostic naming Tier + Locators shape; exit 0 |
| `--attention-gap` area is missing a `Tier:` line or has no locators | Area is silently skipped during parsing — only fully-formed areas are surfaced |
| `--attention-gap` locator `path:` does not exist on disk | Drift row under the area; the area still renders |
| `--attention-gap` locator `kind:` is not seen in ledger projections | Drift row under the area; the area still renders |

## Repository layout

```
.claude/skills/find-orphaned-ideas/
├── SKILL.md                  # this file — orchestrator
└── scripts/
    └── find.py               # the detector (uses _common/ideas_lib.py)
```

## Cross-references

- Schema: `.claude/docs/idea-ledger.md`
- TODO-mode tuning (optional host config): `.claude/docs/todo-tuning.md`
- Attention-gap declarative map (optional host config):
  `.claude/docs/importance-map.md` (shape per ADR 0016)
- Capture skill: `/track-idea`
- Upstream for `--dead-prototype`: `/find-dormant`, `/find-dead-route-surface`
- Bulk writer for surfaced candidates: `/extract-existing-ideas` (which
  calls `/brainstorm-ideas` for dedup + validation)
- ADR motivating this system: `ai-docs/decisions/0013-idea-tracking-system.md`
- ADR for the importance-map shape: `ai-docs/decisions/0016-importance-map-shape.md`
- Shared library: `.claude/skills/_common/ideas_lib.py`
