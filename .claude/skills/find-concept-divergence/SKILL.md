---
name: find-concept-divergence
description: |
  Advisory SUSPECT scan that surfaces concept-name drift between the
  canonical glossary at `.claude/contracts/concepts.yaml` and the
  codebase / docs. Detects three drift bands: `avoid_term_hit` (code
  uses a phrasing the glossary explicitly says is wrong),
  `competing_term_coexistence` (a `flagged_ambiguities` entry has
  multiple `competing_terms` present in the same file — drift the
  glossary author has not yet resolved), and
  `superseded_co_occurrence` (both a deprecated name and its
  `superseded_by:` replacement appear in the same file — rename
  transition drift). Detection only — never edits code or docs.
argument-hint: "[paths... — defaults to common project roots; see SKILL.md]"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: maintenance
job: suspect
best_for: |
  Catching cross-subsystem concept-drift cases (a function/module name
  in one subsystem that conceptually duplicates a canonical name in
  another). Pairs with the canonical glossary at
  `.claude/contracts/concepts.yaml`: if a divergence exists for a
  concept that isn't yet glossary-tracked, the strict scan will miss
  it — add the concept first, then re-run.
not_for: |
  Refactor execution (this is detection only); enforcing renames that
  already have a dedicated lint — set `coverage_lint:` on the
  superseded concept and the scanner will skip co-occurrence noise so
  the lint owns the rename; fuzzy/similarity-based identifier matching
  (deferred — strict canonical-name + avoid-term grep only in v1).
language: any
framework: any
scans: [python, javascript, typescript, markdown, templates]
---

# /find-concept-divergence

You are running an advisory concept-glossary divergence audit. The goal
is to surface places in the codebase or docs where:

1. **avoid-term hits** — code uses a phrasing that the glossary
   explicitly lists under a concept's `avoid:` block (the glossary
   author has said "do not use this phrasing for this concept").
2. **competing-term coexistence** — a file contains multiple
   `competing_terms` from a `flagged_ambiguities` entry (an open
   ambiguity has bled into runtime — two competing names for the same
   concept are co-occurring in the same module).
3. **superseded co-occurrence** — a file mentions both a deprecated
   concept name and its `superseded_by:` replacement (rename
   transition drift; redundant with `coverage_lint:`-declared lints).

This skill is detection-only. It never edits code, docs, or the
glossary; it writes a report under
`reports/find-concept-divergence/scan-<UTC>/` so a follow-up audit can
act on the findings.

## Host-language boundary

The host code language is not a routing constraint: this is a strict textual
glossary scan. It reads `.py`, `.js`, `.ts`, `.tsx`, template/HTML, and prose
files; `.tsx` is included as TypeScript source, not as a separate framework
mode. It does not parse TypeScript, resolve imports, infer types, or judge JSX
runtime behavior. Generated and vendor trees remain excluded by the same
path-level rules as other source languages.

## How success is judged

- The run is graded only by artifacts: pasted command output plus
  `findings.jsonl` and `report.md`. Do not claim concept drift was
  checked without those files.
- The scan verdict is one of `clean`, `real-drift`, `glossary-gap`,
  `noise-only`, or `scan-blocked`. A mixed report may name multiple
  row-level triage labels, but the run-level verdict should state the
  most important next action.
- Every row-level triage decision cites the report row and the relevant
  glossary entry. Code claims without the glossary evidence are not
  enough for a concept-divergence verdict.
- The skill remains read-only. It can recommend a rename, glossary
  update, ADR, exclusion, or lint handoff; it never edits the glossary,
  code, docs, or lint rules in this run.

## Glossary source

The canonical glossary is `.claude/contracts/concepts.yaml`. The
detector reads:

- `concepts[].name`, `concepts[].aliases`, `concepts[].avoid`,
  `concepts[].superseded_by`, `concepts[].source`,
  `concepts[].coverage_lint`
- `flagged_ambiguities[].competing_terms`

If the glossary is missing or unparseable the scan exits with a clear
error rather than degrading silently — concept-divergence detection
has no meaningful default behavior without it.

Copied installs use a schema-specific stdlib profile, not a general YAML
engine: normal block lists and scalar flow lists are supported; quoted flow
values preserve commas (single quotes or JSON-style double quotes). Nested
flow collections and other unsupported shapes stop the scan with a parse error
rather than becoming different search terms. Normalize those entries to the
documented block-list shape before running the scan.

## Schema convention: `competing_terms:` vs overload ambiguities

`competing_terms:` is for terms that genuinely compete *for the same
concept slot* — rename transitions, parallel implementations of the
same thing, or two names that mean the same thing fighting for
canonicality. Band 2 (`competing_term_coexistence`) treats a file
containing 2+ of these as drift, which is the right semantics for
true competition.

Do **not** use `competing_terms:` for **overload** cases where the
named terms are typed names for *distinct things that share a noun*
(e.g. distinct stores with overlapping prose, or distinct entities
that each carry the same generic English word in their slug). For
those, document the typed senses under `where:` and let the
canonical concept's `avoid:` block catch the actual drift signal
(bare generic-noun usage in prose / log strings) via band 1.

## Default target

If the caller does not provide paths, the scanner walks a portable
set of common project roots — language- and framework-agnostic —
and auto-skips any that don't exist in the host repo:

```
app/, src/, lib/, scripts/, tests/, docs/,
.claude/skills/, .claude/docs/,
CONTEXT.md, README.md, ONBOARDING.md,
CLAUDE.md, .claude/CLAUDE.md
```

Out-of-scope paths (always excluded): `.venv/`, `node_modules/`,
`.git/`, `dist/`, `build/`, `__pycache__/`, `.pytest_cache/`,
`.mypy_cache/`, `.ruff_cache/`, `*/migrations/` (Django-shaped),
`ai-docs/decisions/` (ADRs intentionally name both sides of a rename),
`.claude/worktrees/` (agent worktrees), `reports/` (runtime output),
`*.worktree/`. Host projects extend the prefix exclusion list via
`.claude/skills/find-concept-divergence/host_excludes.txt` (one
path-prefix per line; comments via `#`).

Exclusions are evaluated relative to `--project-root`, including a directly
named file or directory. The walk does not follow directory symlinks and
rejects any file/symlink resolving outside that project root. Therefore a host
may itself live below an ancestor named `node_modules`, while its own dependency
tree and escaped symlink targets remain out of scope.

## Pipeline

```bash
SCAN_ID="scan-$(date -u +%Y%m%d-%H%M%S)"
REPORT_DIR="reports/find-concept-divergence/$SCAN_ID"
mkdir -p "$REPORT_DIR"

.venv/bin/python .claude/skills/find-concept-divergence/scripts/scan.py \
  --output "$REPORT_DIR/findings.jsonl" \
  --report "$REPORT_DIR/report.md"
```

Scan targets, finding labels, and the glossary default
(`<project-root>/.claude/contracts/concepts.yaml`) anchor on
`--project-root`, which defaults to the git toplevel of the cwd (else
the cwd).

For a bounded target or non-default glossary, pass the flags explicitly:

```bash
.venv/bin/python .claude/skills/find-concept-divergence/scripts/scan.py \
  --output "$REPORT_DIR/findings.jsonl" \
  --report "$REPORT_DIR/report.md" \
  --glossary .claude/contracts/concepts.yaml \
  .claude/skills/find-concept-divergence
```

The scan writes:

- `findings.jsonl` — one record per hit; fields `band`, `concept` or
  `ambiguity_id`, `file`, `line`, `match`, `term`.
- `report.md` — grouped summary by band, sorted by concept then file.

## Output triage

Classify each finding into one of:

- **real drift** — code says one thing, glossary says another;
  promote to a `quality/findings.jsonl` entry (or the host project's
  equivalent) with band-appropriate recommendation (rename, glossary
  update, ADR).
- **glossary gap** — the term in code is fine but the glossary lists
  a stale `avoid:` phrasing or hasn't registered a real synonym; update
  `concepts.yaml` and re-run.
- **noise** — false-positive (term appears inside a string literal or
  comment that's intentionally quoting deprecated naming). Skip; if
  the same noise recurs across multiple scans, narrow the `avoid:`
  phrase, add the file's prefix to `host_excludes.txt`, or move the
  case to a typed-name `where:` block instead of `competing_terms:`.

If you dispatch an Agent to triage the report, give it this verdict
contract: each row must be labeled `real drift`, `glossary gap`, or
`noise`, and each label must cite both the report row and the glossary
entry. Agent output without those citations is not evidence.

## Strict-first principle

v1 is strict only: it grep-matches the canonical names, aliases, avoid
phrasings, and competing-terms slugs verbatim (word-boundary,
case-insensitive). It does **not** do similarity matching, stem
analysis, or fuzzy identifier comparison. Add similarity flagging
only if the strict pass produces nothing real over multiple cycles.

If the strict pass produces noise, narrow the `avoid:` phrases in
`concepts.yaml` (more specific, more identifier-like) or add a
`host_excludes.txt` entry — don't add heuristics to the body.

## Replay check

After editing this skill or its detector contract, run:

```bash
.venv/bin/python .claude/skills/find-concept-divergence/scripts/scan.py --help
SCAN_ID="scan-replay"
REPORT_DIR="/tmp/find-concept-divergence-${SCAN_ID}"
mkdir -p "$REPORT_DIR"
.venv/bin/python .claude/skills/find-concept-divergence/scripts/scan.py \
  --output "$REPORT_DIR/findings.jsonl" \
  --report "$REPORT_DIR/report.md" \
  .claude/skills/find-concept-divergence
```

This bounded self-scan is the replay case for text/contract repairs. It
proves the documented argparse surface and output contract execute
against the current glossary; it does not prove the full repo is clean.

## When things go sideways

| Symptom | Action |
|---|---|
| `.claude/contracts/concepts.yaml` is missing or unparseable | Mark `scan-blocked`, paste the error, and stop; concept-divergence has no useful fallback without the glossary. |
| The report has hits but the glossary entry is ambiguous | Use row label `glossary gap`, cite the entry, and recommend updating `concepts.yaml` before renaming code. |
| A hit appears only in a deliberate quote of deprecated terminology | Label it `noise`, cite the surrounding line, and only add an exclusion if the same noise recurs. |
| A superseded concept declares `coverage_lint` | Treat that lint as owning the rename guard; do not double-count skipped co-occurrence noise as scanner drift. |
| Agent triage omits glossary citations | Reject the dispatch output and read the report/glossary directly. |
