---
name: find-standard-gaps
description: Detect places a declared baseline standard should apply but doesn't. A standard (a security check, a resilience rule, an input-validation or observability requirement) is declared once as an idea with an executable `ast` detector; `scan_coverage.py` then scans the tree and reports every site whose triggering situation holds but the standard is absent. Generalizes hand-written AST lints — declare a standard instead of authoring a bespoke lint. Detection-only; never edits code.
argument-hint: "[standards-file — defaults to standards/standards.json; ships as standards.example.json to copy + adapt]"
allowed-tools: Bash, Read, Grep, Glob, Write
user-invocable: true
tier: maintenance
job: suspect
best_for: |
  Checking that a baseline standard is applied everywhere its situation
  occurs — "every external DB connection is inside a try", "every
  outbound HTTP call sets a timeout", "no call to X without guard Y".
  Each standard is a declarative entry with an `ast` detector; the scan
  is deterministic, cheap, and syntactically precise.
not_for: |
  Judgment-heavy ideas that do not reduce to a call/argument/block
  pattern (keep those as code review). Structural smells — omnibus,
  duplication, dormant code (use the find-* family). Executing the
  fixes (hand off to /fix-workflow). Authoring a bespoke one-off lint
  when no standard will be reused (just write the lint).
language: python
---

# /find-standard-gaps

You are the orchestrator for a SUSPECT skill. Given a **standards file**
— a JSON file of declared baseline standards, each carrying an
executable detector — you scan the codebase and report every
**coverage gap**: a site where a standard's triggering situation holds
but the standard is not applied.

This is the value-coverage idea made operational: a good standard is
worth nothing at the sites that don't use it. The skill generalizes the
project's hand-written AST lints — instead of authoring one lint per
rule, a rule is declared once as a standard and coverage-checked.

The skill is **deterministic** — `scripts/scan_coverage.py` does the
work; there is no scout fan-out. The detector model (how `ast` and
`grep` detectors work, why `ast` is preferred) is in
`knowledge/detector-model.md`.

## Core beliefs

1. **Absence is the finding.** Structural skills audit code that
   exists; this one finds a standard that *should* be at a site and
   isn't. That is a different, complementary question.
2. **`ast` over `grep`.** An `ast` detector is syntactically precise —
   it never matches a comment or a string literal. `grep` is a fallback
   for genuinely lexical patterns only. See `knowledge/detector-model.md`.
3. **A gap is not a verdict.** A flagged gap is high-confidence "the
   standard is not applied here" — not "this is a bug." Some gaps are
   deliberate exceptions. Triage is a fix-time decision.
4. **A clean standard is a result.** A standard with 0 gaps is a
   passing standard — it confirms the codebase upholds the rule, and
   the scan becomes a regression guard if re-run.

## Scope

- **Project root:** the repository root.
- **Python:** `python3` — `scan_coverage.py` is stdlib-only.
- **Output:** `reports/standard-gaps/scan-<TS>/` only. Never edits code.

## Argument

The argument is an optional path to a standards file. Default:
`.claude/skills/find-standard-gaps/standards/standards.json`.

This skill ships **`standards/standards.example.json`** — a template
with two universal example standards. On first use, copy it to
`standards.json` and adapt: narrow each detector's `paths` to your
source root, and replace the examples with the baseline standards your
codebase should uphold. The file shape and the detector model are in
`knowledge/detector-model.md`.

## Pipeline

### Stage 0 — Setup

```bash
TS=$(date +%Y%m%d-%H%M%S)
REPORT_DIR="reports/standard-gaps/scan-${TS}"
mkdir -p "$REPORT_DIR"
STANDARDS="<argument, or .claude/skills/find-standard-gaps/standards/standards.json>"
```

### Stage 1 — Scan

```bash
python3 .claude/skills/find-standard-gaps/scripts/scan_coverage.py \
  --ideas "$STANDARDS" \
  --project-root "$(pwd)" \
  --output-dir "$REPORT_DIR"
```

`scan_coverage.py` runs each standard's detector against the tree and
writes `coverage.md` (human report) and `coverage.json` (machine). It
recognises `ast` (`enclosed_by` / `requires_kwarg`) and `grep`
detectors; `manual`/`skill` standards are reported as skipped.

### Stage 2 — Summarize

Read `coverage.md`. Report to the user in ≤10 lines:

- per standard: situation-site count, gap count, coverage %;
- the highest-priority gaps (a security/resilience standard with gaps
  outranks a style one);
- standards that came back **clean** (0 gaps) — name them, that is a
  positive result;
- path to `${REPORT_DIR}/coverage.md`.

### Stage 3 — Hand off

- Genuine gaps on a security/resilience standard → `/fix-workflow` with
  the gap list, or spin off a triage task.
- A standard that is mostly-clean with a couple of gaps → fix inline.
- A standard you keep wanting → add it to the standards file so every
  future run checks it. The standards file is the durable artifact.

## When the target language isn't supported

The `ast` detector is **Python-only** (it is CPython's `ast` module).
When a standard's `paths` match files but none are `.py`,
`scan_coverage.py` reports that standard as **`language_unsupported`** —
*not* as "0 gaps". **Treat `language_unsupported` as "could not
analyze", never as "compliant".** A silent "0 gaps" on an unanalyzable
language is the one genuinely dangerous failure mode of this skill.

When a standard comes back `language_unsupported`, apply this rule:

1. **Enumerate the situation sites cheaply.** A plain `grep` for the
   call or pattern works in any language — it tells you how many places
   the standard *could* apply.
2. **Branch on size:**
   - **Small** — a bounded surface (rule of thumb: ≤ ~20 situation
     sites, readable in one pass): read those files directly, judge the
     standard by hand, and report the gaps **explicitly marked "manual
     review — not tool-verified"**.
   - **Large** — more sites than that, or the situation can't be cheaply
     grepped: **stop. Do not hand-scan a large surface** — it is
     unreliable and burns context for a low-confidence result.
     Recommend **building the detector tooling first** — a
     tree-sitter-backed `scan_coverage`, or a language-specific AST pass
     — then re-running. An honest "tooling needed" beats a
     half-finished manual sweep.

The principle: **small → read directly; large → build the tooling
first.** A `grep` detector still runs on any language, but it is
comment/string-blind — trust it for *enumerating* situations, not for
deciding satisfaction.

## Non-goals

- Editing or fixing code — detection only.
- Scout-verifying gaps — the `ast` detector is the precision; triage is
  downstream.
- Re-deriving structural smells — that is the `find-*` family.
- Replacing real lints for a one-off rule — a standard pays off when it
  is reused; a single-use rule is just a lint.

## When things go sideways

| Symptom | Action |
|---|---|
| A standard reports a huge gap count | The detector is too broad, or the situation regex matches non-code — tighten `call_matches`, or switch a `grep` standard to `ast` |
| A `grep` standard flags comments/strings | Expected — `grep` is comment/string-blind. Convert it to an `ast` detector |
| 0 standards scanned | All standards are `manual`/`skill`, or the standards file has no `ideas` array |
| A gap is a deliberate exception | Not a tool failure — note it at fix time; a future `--allow` list could record approved exceptions |

## Repository layout

```
.claude/skills/find-standard-gaps/
├── SKILL.md                  # this file — orchestrator
├── scripts/
│   └── scan_coverage.py      # the scan — deterministic, stdlib-only
├── knowledge/
│   └── detector-model.md     # the detector model + how to add a standard
└── standards/
    └── standards.example.json  # template — copy to standards.json and adapt
```
