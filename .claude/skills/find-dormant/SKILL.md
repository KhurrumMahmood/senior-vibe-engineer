---
name: find-dormant
description: Detect dead and quasi-dead code. Runs vulture + AST "defined but never referenced" checks, validates every candidate against real call sites, cross-references URL patterns with template URL-name usage, runs a git-log recency check, and produces a deletion-candidates report with evidence. Never deletes unilaterally — surfaces findings for user authorization, then hands off to `/fix-workflow`.
argument-hint: "--target <directory>"
allowed-tools: Bash, Read, Grep, Glob, Write, Edit, Agent
user-invocable: true
tier: maintenance
job: suspect
best_for: |
  Detecting dead and quasi-dead Python code, unused URL patterns,
  defined-but-unreferenced symbols. Validates against real call sites
  and template URL-name usage; cross-checks git-log recency. Never
  deletes — surfaces evidence for /fix-workflow delete:<id>.
not_for: |
  Removing flagged code (use /fix-workflow delete:<id>). Architectural
  smells like omnibus or layer violation (use those /find-* skills).
  Semantic duplication where two implementations coexist (use
  /find-semantic-duplication).
language: python
framework: django
scout_model: cheap
---

# /find-dormant

You are the **orchestrator** for a dormant-code audit. Your job is to
drive a pipeline of detectors and sub-agent verifiers; the judgment
calls live in the scout brief and the knowledge files, not in this
prompt.

The four flavors of dormant (literal-dead, orphan-endpoint,
silently-broken, orphan-entry-with-live-internals) and the 6-step
verification are documented in
`knowledge/verification.md` — scouts read it, you don't.

## Scope

- **Target path:** the required `--target` argument. Must be a
  directory.
- **Project root:** this worktree's root.
- **Python:** `.venv/bin/python` (never bare `python`).
- **Project-specific defaults** (grep locations, Django false
  positives, dynamic-dispatch patterns, candidate skip list): in
  `knowledge/`.

## Feature Graduation Sweep

Run a focused dormant sweep after a prototype graduates into a real
workflow or after a page/JS entry point is removed. Dead prototype
templates, routes, and static JS with no unique product knowledge
should be deletion candidates, not kept alive with compatibility
aliases. Git history is the archive; live code should be loaded,
explicitly quarantined with a reason, or removed.

## Pipeline stages (each has a contract)

Each stage reads files the previous stage wrote and writes files the
next stage reads. Run scripts with `.venv/bin/python` and capture
stderr so failures surface.

### Stage 0 — Setup

**Pre:** none. **Post:** `${REPORT_DIR}` exists, `latest` symlink
points to it.

```bash
TS=$(date +%Y%m%d-%H%M%S)
REPORT_DIR="reports/dormant/scan-${TS}"
mkdir -p "${REPORT_DIR}/scout"
ln -sfn "scan-${TS}" reports/dormant/latest
```

### Stage 1 — Detect (four in parallel)

**Pre:** target directory exists. **Post:** four files present:
`vulture.txt`, `url_patterns.jsonl`, `unreferenced_defs.jsonl`,
`silent_catches.jsonl`.

Run all four commands concurrently in one Bash message. None depends
on another — they all write independent outputs that collapse merges.

```bash
# 1. vulture — standard dead-code tool, min-confidence 80 for precision.
#    `|| true` because vulture exits non-zero on any finding.
.venv/bin/python -m vulture <target> \
  --min-confidence 80 \
  --exclude "migrations/,tests_*.py,test_*.py,vendor_*.py,staticfiles/,sites/*/scrape.py" \
  > "${REPORT_DIR}/vulture.txt" 2>&1 || true

# 2. URL patterns — for the orphan-endpoint check. Follows include() to
#    find patterns defined in api_urls.py, admin_urls.py, etc.
.venv/bin/python .claude/skills/find-dormant/scripts/detect_urls.py \
  --root-urls <path/to/urls.py> \
  --project-root "$(pwd)" \
  --output "${REPORT_DIR}/url_patterns.jsonl"

# 3. AST "defined but never referenced" — errs toward candidates;
#    scouts do the real verification.
.venv/bin/python .claude/skills/find-dormant/scripts/detect_unreferenced.py \
  --target <target> \
  --project-root "$(pwd)" \
  --output "${REPORT_DIR}/unreferenced_defs.jsonl"

# 4. Silent catches — Flavor-3 detector. Every `except Exception: pass`
#    / `return None` / `continue` / log-and-return handler in the tree.
.venv/bin/python .claude/skills/find-dormant/scripts/detect_silent_catches.py \
  --target <target> \
  --project-root "$(pwd)" \
  --output "${REPORT_DIR}/silent_catches.jsonl"
```

### Stage 2 — Collapse

**Pre:** all four Stage-1 outputs. **Post:** `${REPORT_DIR}/candidates.jsonl` —
one record per candidate with `candidate_id`, `sources`, `hints`.

Silent catches stay as their own candidates. Vulture and unreferenced
dedupe when they flag the same (file, line, name). URL patterns are
passed through as a lookup table the scout reads in 6a; they do not
become standalone candidates.

```bash
.venv/bin/python .claude/skills/find-dormant/scripts/collapse.py \
  --vulture "${REPORT_DIR}/vulture.txt" \
  --url-patterns "${REPORT_DIR}/url_patterns.jsonl" \
  --unreferenced "${REPORT_DIR}/unreferenced_defs.jsonl" \
  --silent-catches "${REPORT_DIR}/silent_catches.jsonl" \
  --output "${REPORT_DIR}/candidates.jsonl"
```

### Stage 3 — Verify (parallel fan-out)

**Pre:** `candidates.jsonl`. **Post:** `${REPORT_DIR}/scout/<candidate_id>.json`
for every verified candidate.

This is the **only stage where LLM judgment runs**. You do not verify
candidates yourself — dispatch one sub-agent per candidate (or batch
if there are many). Each sub-agent receives:

- the candidate JSON (one line from `candidates.jsonl`),
- the prompt template from `agents/verify.md`,
- paths to `knowledge/*` files and `url_patterns.jsonl`,
- an output path it must write to.

**Budget:** verify up to **25 candidates by default**, prioritizing in
this order:

1. **silent_catches first** — Flavor-3 surfaces hide real bugs.
2. **unreferenced with `url_wired_hint: true`** — likely orphan
   endpoints (Flavor 2/4).
3. **vulture ∪ unreferenced** — literal-dead candidates (Flavor 1).

If the user asked for a deeper scan, raise the budget. If the user
asked for a specific subset (e.g., "only the silent catches"), filter
before dispatch.

For each candidate, expand `agents/verify.md` (substitute
`{{candidate_id}}`, `{{candidate_json}}`, `{{project_root}}`,
`{{skill_root}}`, `{{url_patterns_path}}`, `{{output_path}}`) and
dispatch with `subagent_type=general-purpose`. Send all Agent calls in
a **single message** so they run concurrently.

If a scout returns invalid JSON or flags the verification as aborted,
re-dispatch once with a stricter "respond only with file-write
confirmation" nudge; skip the candidate if it fails twice.

#### Dispatch mode — Agent tool vs cheap subprocess

This skill declares `scout_model: cheap` — the verify step is read-and-
classify against the four flavors in `verify.md`, no cross-file
synthesis, no shell. That makes it safe on Haiku-class scouts and the
right place to dogfood the cheap-fan-out path.

For nesting-safe + low-cost fan-out, dispatch each candidate as a
`tools/code_agent.py --read-only` subprocess via
`.claude/skills/_common/dispatch_scout_cheap.sh`. The `--read-only`
flag drops bash, spawn_agent, claude_tools, and validate_jsonld — the
scout has only read_file/write_file/glob/grep, with workdir
containment enforced (commit `168ca3c1`). Cheap models can't
hallucinate calls to tools that aren't in the registry.

```bash
# One subprocess per candidate; parallelize with `&` + wait.
while read -r line; do
    cid=$(jq -r '.candidate_id' <<<"$line")
    out="${REPORT_DIR}/scout/${cid}.json"
    .claude/skills/_common/dispatch_scout_cheap.sh \
        .claude/skills/find-dormant/agents/verify.md \
        "$out" \
        candidate_id="$cid" \
        candidate_json="$(jq -c . <<<"$line")" \
        project_root="$(pwd)" \
        skill_root=".claude/skills/find-dormant" \
        url_patterns_path="${REPORT_DIR}/url_patterns.jsonl" \
        output_path="$out" &
done < "${REPORT_DIR}/candidates.jsonl"
wait
```

**Tradeoffs.** Cheap subprocess dispatch adds ~2-4s spawn per scout
and runs Claude Haiku 4.5 through the team's Expedient gateway by
default (see `tools/agent-config.json`); set `DISPATCH_SCOUT_MODEL`
to swap in any other alias (e.g., `cerebras` for personal-account
free-tier capacity). The `Agent` tool path is faster (~0s spawn) and
uses the orchestrator's session model (Sonnet/Opus tier — more
judgment, billed). Use the cheap subprocess by default; fall back to
`Agent` when (a) only a handful of candidates need verification
interactively and the user is watching, or (b) a candidate's flavor
is genuinely ambiguous and warrants the better model.

### Stage 4 — Report

**Pre:** `candidates.jsonl`, `scout/*.json`. **Post:**
`${REPORT_DIR}/report.md` and `${REPORT_DIR}/findings.json`.

```bash
.venv/bin/python .claude/skills/find-dormant/scripts/report.py \
  --scout-dir "${REPORT_DIR}/scout" \
  --candidates "${REPORT_DIR}/candidates.jsonl" \
  --output-md "${REPORT_DIR}/report.md" \
  --output-json "${REPORT_DIR}/findings.json" \
  --scan-id "scan-${TS}" \
  --target <target>

# Effectiveness log — one line per run, feeds reports/_meta/dashboard.md.
# Buckets come straight from findings.json's summary.buckets field
# (certain_delete / orphan_endpoint / quasi_dead_broken / false_positive /
# unverified_budget). See `.claude/skills/_common/skill-conventions.md`.
python3 scripts/log_effectiveness.py \
  --skill find-dormant \
  --scan-id "scan-${TS}" \
  --target <target> \
  --findings-total "$(.venv/bin/python -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d.get("summary",{}).get("findings_total", len(d.get("findings", []))))' "${REPORT_DIR}/findings.json")" \
  --buckets "$(.venv/bin/python -c 'import json,sys; print(json.dumps(json.load(open(sys.argv[1])).get("summary",{}).get("buckets", {})))' "${REPORT_DIR}/findings.json")"
```

### Stage 5 — Summarize

Report to the user in ≤10 lines:

- counts by bucket (certain_delete / orphan_endpoint / quasi_dead_broken / false_positive),
- top 3 candidates (one line each: name, file:line, recommendation),
- any `external_api_risk: true` orphan-endpoint flags (webhooks need
  human confirmation),
- path to `${REPORT_DIR}/report.md` and the `latest` symlink,
- recommended next slash command (`/fix-workflow delete:<name>`,
  `/fix-workflow fix:<name>`, or `/find-dormant` again after cleanup).

The report is the source of truth — do not enumerate every candidate.

## Non-goals

- Executing deletions (that's `/fix-workflow` after user authorization).
- Fixing silently-broken code (surface it, recommend
  `/fix-workflow fix:<name>`).
- Refactoring adjacent code.
- Running tests — read-only audit; tests run during `/fix-workflow`.
- Detecting duplication (that's `/find-duplication` /
  `/find-semantic-duplication`).
- CI gates — periodic audit, not a per-commit check.

## When things go sideways

| Symptom | Action |
|---|---|
| Stage 1 vulture missing | `pip install vulture` into `.venv`; or skip `--vulture` flag in Stage 2 — unreferenced+silent_catches still produce candidates |
| Stage 1 detect_urls reports 0 patterns | Check the root URLconf exists; re-run with `--root-urls` pointing at the right file |
| Stage 1 detect_unreferenced is slow | Each def triggers a `git grep` — expect 1–2 minutes on a large source tree (10k+ defs). Reduce scope with a smaller `<target>` |
| Stage 2 reports 0 candidates | Target has no orphans (best outcome) — or detectors all failed; check stderr from each Stage-1 command |
| Stage 3 scout buckets everything as `false_positive` | Scout is being too conservative; inspect one output and re-dispatch with tighter instruction |
| Scout flags webhook-shaped URL as `certain_delete` | Rule 2 in `verify.md` was skipped — re-dispatch citing `external_api_risk` |
| Report's `recommendation` field disagrees with bucket | Scout error; reconcile using the cheat-sheet in `agents/verify.md` |

## Repository layout

```
.claude/skills/find-dormant/
├── SKILL.md                         # this file — orchestrator
├── scripts/
│   ├── detect_urls.py               # Stage 1
│   ├── detect_unreferenced.py       # Stage 1
│   ├── detect_silent_catches.py     # Stage 1
│   ├── collapse.py                  # Stage 2
│   └── report.py                    # Stage 4
├── agents/
│   └── verify.md                    # Stage 3 scout brief
└── knowledge/                       # sub-agent context, never loaded by orchestrator
    ├── verification.md
    └── learnings.md
```

The orchestrator (you) **never reads files in `knowledge/`**. Those
are for the scout sub-agents. Keeping them out of your context is the
whole point of this architecture.
