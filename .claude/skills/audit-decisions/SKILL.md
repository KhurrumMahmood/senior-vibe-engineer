---
name: audit-decisions
description: "Cross-cutting drift scanner for the decision registry. Wraps `scripts/decisions.py audit --json` + `link-check`, then layers four checks the script doesn't run on its own — `# decision:NNNN` code references vs registry, broken supersedes chains, `proposed`-status decisions older than 30 days, `applies_to:` paths that no longer exist on disk. Output: `reports/audit-decisions/scan-<TS>/drift.md` with one row per drift symptom and a recommended next command for each. Read-only — never edits ADRs or production code."
argument-hint: "  (no args; runs across all decisions in ai-docs/decisions/)"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: cross-cutting
job: guard
best_for: |
  Periodic (monthly / pre-release) hygiene of the decision registry.
  Catches three classes of rot the registry-as-substrate can develop:
  (a) code references to ADRs that have been deleted/renumbered,
  (b) supersession chains that break (A superseded by B; B doesn't
  exist or doesn't claim to supersede A), (c) decisions that stalled in
  `proposed` and were never accepted-or-deprecated. Use after a batch
  of refactors that shuffled `applies_to:` paths.
not_for: |
  Authoring new ADRs (use /decide). Detecting code-level smells (use a
  find-* SUSPECT skill). Resolving the drift this skill surfaces — the
  user invokes the recommended next command per row (/decide
  --supersede, /decide --status, etc.).
escalate_to: |
  None — this is a read-only scanner. Each drift row names the
  resolution command; the user picks one and proceeds.
delegate_from: |
  /which-skill recommends /audit-decisions for prompts like "is the
  decision registry healthy", "are any ADRs stale", "did we orphan any
  # decision: refs". /triage-debt's decision-drift signal also points
  here for full context.
language: python
framework: django
---

# /audit-decisions

You are the **orchestrator** for the cross-cutting decision-registry
guard skill. The deliverable is `reports/audit-decisions/scan-<TS>/drift.md`
listing every drift symptom with one resolution command per row. You do
NOT author ADRs, do NOT edit production code, do NOT mutate the
registry — you SURFACE drift, the user FIXES it.

The skill is the standing complement to `/decide`: `/decide` keeps the
registry growing in a sound shape, `/audit-decisions` keeps it from
rotting after the fact.

## Core beliefs

1. **The substrate has its own gravity.** Every `# decision:NNNN`
   inline reference is a load-bearing claim that the ADR exists, says
   what the ref author thought it said, and still applies. Drift in any
   of those three is real debt.
2. **Stalled `proposed` is the most common rot.** Teams write a
   `proposed` ADR during a debate, the debate ends, no one updates the
   status. After 30 days the registry can't tell "still being decided"
   from "we forgot".
3. **Broken supersession is the most dangerous rot.** An ADR that
   claims `superseded_by: 0042` when 0042 doesn't exist (or doesn't
   claim to supersede it back) leaves callers reading the old decision
   and acting on dead guidance.
4. **`applies_to` paths rot quietly.** A refactor renames
   `core/services/foo.py` → `core/services/bar/foo.py` and the ADR's
   `applies_to: [core/services/foo.py]` is now wrong. Code refs lie
   silently until someone re-greps.

## Scope (this skill itself)

- **Project root:** this worktree's root.
- **Python:** `python3` (stdlib-only).
- **Read:** `ai-docs/decisions/` (full),
  `python3 scripts/decisions.py audit --json`,
  `python3 scripts/decisions.py link-check`,
  every code file under the project root (for `# decision:NNNN`
  reference grep).
- **Write:** `reports/audit-decisions/scan-<TS>/drift.md`,
  `reports/audit-decisions/scan-<TS>/raw-drift.json` (per-row evidence).

## Pipeline

### Stage 0 — Setup

```bash
TS=$(date +%Y%m%d-%H%M%S)
REPORT_DIR="reports/audit-decisions/scan-${TS}"
mkdir -p "${REPORT_DIR}"
ln -sfn "scan-${TS}" reports/audit-decisions/latest
```

### Stage 1 — Run the registry's own audit

```bash
python3 scripts/decisions.py audit --json > "${REPORT_DIR}/registry-audit.json"
python3 scripts/decisions.py link-check >  "${REPORT_DIR}/link-check.txt" 2>&1 || true
```

Read `registry-audit.json`. Capture every entry from `drift[]`. These
are the drift symptoms the registry script catches on its own
(typically: missing supersedes target, missing superseded_by target,
duplicate ids).

### Stage 2 — Layer the four extra checks

#### 2a. `# decision:NNNN` code references vs registry

Grep the project for inline references:

```bash
grep -rn "# decision:" --include='*.py' --include='*.md' --include='*.html' \
    --exclude-dir=.venv --exclude-dir=node_modules \
    --exclude-dir=.git --exclude-dir=reports . \
  > "${REPORT_DIR}/code-refs.txt"
```

For each referenced id, check it exists in the registry. If not, that's
a drift row:

- Symptom: `code-ref-orphan` — code at `<file>:<line>` references
  `decision:NNNN` but no such ADR exists.
- Resolution: `/decide <slug>` to author the missing ADR, OR remove the
  ref if the rule has been retired.

Also check the converse: every accepted ADR ought to have at least one
inline reference somewhere (code, doc, or skill). An ADR with zero
references after 60 days is suspect.

- Symptom: `unreferenced-decision` — ADR `NNNN` (`<title>`) is
  `accepted`, > 60 days old, and has no inline references.
- Resolution: low priority — note for review; consider deprecating if
  the rule is no longer load-bearing.

#### 2b. Broken supersession chains

For each ADR with `supersedes: [...]` or `superseded_by: ...`:

- If `superseded_by: 0042`, confirm 0042 exists AND its `supersedes:`
  list contains this ADR's id. If not, drift row:
  - Symptom: `broken-supersession` — `NNNN` claims to be superseded by
    `0042` but `0042` doesn't claim to supersede it back.
  - Resolution: `/decide --amend 0042` to fix the back-reference.

- If `supersedes: [0010]`, confirm 0010's `superseded_by:` matches.
  Same shape if not.

#### 2c. Stalled `proposed` decisions

For each ADR with `status: proposed`:

- If `date:` is older than 30 days, drift row:
  - Symptom: `proposed-too-long` — `NNNN` (`<title>`) has been
    `proposed` for `<N>` days.
  - Resolution: `/decide --status accepted NNNN` if the team decided
    yes, `/decide --status deprecated NNNN` if no, or amend the ADR if
    still being debated (and reset the date).

#### 2d. `applies_to:` paths missing

For each ADR with `applies_to: [path1, path2, ...]`:

- For each path, check `os.path.exists(path)`. If missing, drift row:
  - Symptom: `applies-to-missing` — `NNNN` says `applies_to:
    <path>` but the path no longer exists.
  - Resolution: `/decide --amend NNNN` to update the path (likely a
    refactor moved the target).

Allow a glob pattern in `applies_to:` (e.g., `core/services/*.py`); for
those, check that at least one match exists.

### Stage 3 — Aggregate into `drift.md`

```markdown
# Decision-registry drift — scan-<TS>

_<N> ADRs scanned. <M> drift rows surfaced._

## Summary
| Symptom | Count | Severity |
|---|---|---|
| broken-supersession | 0 | P0 |
| code-ref-orphan | 0 | P0 |
| applies-to-missing | 0 | P1 |
| proposed-too-long | 0 | P1 |
| unreferenced-decision | 0 | P2 |

## Drift rows

### P0 — fix before next release

(empty if none)

### P1 — fix this sprint

- `proposed-too-long` — ADR `0007` (`use-cerebras-for-bulk-llm`),
  proposed 2026-03-01, `<N>` days stale.
  - Resolution: `/decide --status accepted 0007` or `/decide --status
    deprecated 0007`.

### P2 — review when convenient

- `unreferenced-decision` — ADR `0002` (`spec-first-refactor`),
  accepted 2026-04-30, no inline `# decision:0002` references found.
  - Resolution: review whether the rule is still load-bearing; if so,
    add `# decision:0002` to the affected files.

## Notes for the user

- Re-run after applying resolutions to confirm clean.
- `/triage-debt` will pick up unresolved P0/P1 in its decision-drift
  signal until fixed.
```

### Stage 4 — Severity rules

| Symptom | Default severity | Override |
|---|---|---|
| broken-supersession | P0 | none — always P0 |
| code-ref-orphan | P0 | downgrade to P1 only if the orphan is in a doc, not code |
| applies-to-missing | P1 | upgrade to P0 if all paths are missing (the ADR is dangling) |
| proposed-too-long | P1 | upgrade to P0 if > 90 days |
| unreferenced-decision | P2 | upgrade to P1 if the ADR has `tags: [lint, enforced]` (an enforced rule with no refs is suspicious) |

Severity is advisory — the user re-prioritizes based on context.

### Stage 5 — Write `raw-drift.json`

For every drift row, capture the full evidence in a JSON sibling file
so the heuristic is debuggable and downstream skills (e.g.,
`/triage-debt`) can consume the structured form:

```json
{
  "scan_id": "scan-<TS>",
  "drift": [
    {
      "symptom": "proposed-too-long",
      "severity": "P1",
      "adr_id": "0007",
      "adr_slug": "use-cerebras-for-bulk-llm",
      "evidence": {"date": "2026-03-01", "days_old": 61},
      "resolution_command": "/decide --status accepted 0007"
    }
  ]
}
```

### Stage 6 — Summarize

Report to the user in ≤6 lines:

- Path to `drift.md`.
- Drift rows by severity (`P0: N, P1: M, P2: K`).
- 1-line for the top P0 (or "no P0 drift" if clean).
- Recommended next command:
  - If clean: "registry healthy — no action".
  - Else: "address P0 first via the resolutions in drift.md".

## Non-goals

- Authoring or amending ADRs (that's `/decide`).
- Detecting code-level smells (that's `/find-*`).
- Editing production code or the registry.
- Mutating decision status (the user decides; this skill surfaces).

## When things go sideways

| Symptom | Action |
|---|---|
| `decisions.py audit --json` fails | Capture stderr to `${REPORT_DIR}/registry-audit.err`, surface as a P0 drift row "registry-script-broken" — the audit can't trust itself if the substrate script is broken |
| Code-ref grep returns thousands of hits | Likely a false-positive pattern (e.g., `# decision:` in third-party code); narrow the grep with `--include` paths in `core/`, `.claude/`, `ai-docs/` |
| `applies_to:` is missing entirely on an ADR | Drift row: `applies-to-missing` with severity P1; recommend `/decide --amend NNNN` to add the field |
| Every accepted ADR is unreferenced | The team isn't using inline refs yet; downgrade all `unreferenced-decision` to P3-info and note "consider adopting `# decision:NNNN` convention" |
| Two ADRs have the same id | Drift row: `duplicate-id` (P0); recommend renumbering one via `/decide --renumber` |
| ADR's `superseded_by` points to itself | Drift row: `circular-supersession` (P0); recommend `/decide --amend` to break the cycle |
