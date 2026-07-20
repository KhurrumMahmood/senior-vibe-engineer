---
name: find-standard-gaps
description: Detect places a declared baseline standard should apply but doesn't. A standard is declared once with an executable `ast` detector; `scan_coverage.py` scans Python and narrow syntax-only JavaScript/TypeScript direct-call coverage and reports every site whose triggering situation holds but the standard is absent. Detection-only; never edits code.
argument-hint: "<host-owned standards JSON — copy standards.example.json, adapt it, and pass its path>"
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
  Census mode (scripts/census.py) answers the upstream discovery question:
  "what variants exist, which is the majority, who are the stragglers?"
  Use census before declaring a standard to understand the current
  population; census output feeds /decide and standards declaration.
not_for: |
  Judgment-heavy ideas that do not reduce to a call/argument/block
  pattern (keep those as code review). Structural smells — omnibus,
  duplication, dormant code (use the find-* family). Executing the
  fixes (hand off to /fix-workflow). Authoring a bespoke one-off lint
  when there is no reusable baseline policy (just write the lint).
language: any
framework: any
scans: [python, javascript, typescript]
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

## How success is judged

- `coverage.md` and `coverage.json` agree on every standard's status.
  Grade the run by these artifacts plus the pasted `scan_coverage.py`
  stdout/stderr, not by an executor's claim that the scan "passed".
- `coverage.md` enumerates every in-scope standard's coverage cells —
  situation-site count, gap count, coverage % — with no standard silently
  dropped (`manual`/`skill` standards reported as skipped).
- Each standard carries an explicit analyzability verdict:
  `gated_out`, `language_unsupported`, `no_files_matched`, `partial`, and `error`
  are surfaced as non-passing statuses, never passed off as 0 gaps /
  compliant.
- Clean standards are named as positive results only when their status is
  `scanned` and their gap count is 0.
- No production edits — the run writes only under
  `reports/standard-gaps/scan-<TS>/`.

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
4. **A clean standard is a result.** A standard with 0 gaps, 0 skipped files,
   and 0 unsupported matched files is a passing standard — it confirms the
   codebase upholds the rule, and the scan becomes a regression guard if
   re-run.

## Scope

- **Project root:** the repository root.
- **Python:** `scan_coverage.py`, `project_state.py`, and `census.py` are
  stdlib-only; use the host `.venv/bin/python` when it exists, otherwise
  `python3`.
- **TypeScript/TSX v1:** Node plus a `typescript` package resolvable from
  the host project's `package.json`. The bundled Compiler API launcher uses
  `createSourceFile`; it does not read a tsconfig, construct a Program, or
  infer framework behavior.
- **Output:** `reports/standard-gaps/scan-<TS>/` only. Never edits code.

## Installed command

Copy `standards/standards.example.json` to a host-owned `standards.json`,
adapt its `paths` and standards, then set `STANDARDS=standards.json`. Run the
following two blocks verbatim from the host root. They support both the stock
`.agents` projection and this source checkout.

<!-- installed-command:resolve:start -->
```bash
SKILL_ROOT=""
for SKILL_CANDIDATE in \
  ".agents/skills/find-standard-gaps" \
  ".claude/skills/find-standard-gaps"
do
  if [ -f "${SKILL_CANDIDATE}/SKILL.md" ]; then
    SKILL_ROOT="$(cd "${SKILL_CANDIDATE}" && pwd)"
    break
  fi
done
if [ -z "${SKILL_ROOT}" ]; then
  printf '%s\n' "find-standard-gaps is not installed in .agents/skills or .claude/skills" >&2
  exit 2
fi
if [ -x ".venv/bin/python" ]; then
  HOST_PYTHON="$(pwd)/.venv/bin/python"
else
  HOST_PYTHON="python3"
fi
```
<!-- installed-command:resolve:end -->

<!-- installed-command:run:start -->
```bash
: "${STANDARDS:?Set STANDARDS to the host-owned standards JSON file}"
TS=$(date +%Y%m%d-%H%M%S)
REPORT_DIR="reports/standard-gaps/scan-${TS}"
mkdir -p "${REPORT_DIR}"
"${HOST_PYTHON}" "${SKILL_ROOT}/scripts/scan_coverage.py" \
  --ideas "${STANDARDS}" \
  --project-root "$(pwd)" \
  --output-dir "${REPORT_DIR}"
```
<!-- installed-command:run:end -->

## Argument

The argument is an optional path to a host-owned standards file. In a source
checkout the historical default is
`.claude/skills/find-standard-gaps/standards/standards.json`; a stock install
must not write into `.agents`, so use `standards.json` at the host root (or
another explicit host path) through `STANDARDS`.

This skill ships **`standards/standards.example.json`** — a template
with two universal example standards. On first use, copy it to
`standards.json` and adapt: narrow each detector's `paths` to your
source root, and replace the examples with the baseline standards your
codebase should uphold. The file shape and the detector model are in
`knowledge/detector-model.md`.

Standards may include an `activation` block (ADR 0020 shape):
`{"baseline": true}` or `{"rungs": [{"min_maturity": "...",
"min_stakes": "..."}]}`. `scan_coverage.py` gates each standard against
the project state before running the detector.

Project state is read from `.engineering/project-state.json`, falling
back to the legacy `.project-state.json`. If no state file exists, the
script assumes MAX (`production` / `public-adversarial`) and prints a
warning so no standard is silently skipped. To test a specific state
surface, pass `--project-state <path>` explicitly.

## Pipeline

### Stage 0 — Setup

```bash
STANDARDS="<host-owned standards file, commonly standards.json>"
```

### Stage 1 — Scan

```bash
"${HOST_PYTHON}" "${SKILL_ROOT}/scripts/scan_coverage.py" \
  --ideas "$STANDARDS" \
  --project-root "$(pwd)" \
  --output-dir "$REPORT_DIR"
```

`scan_coverage.py` runs each standard's detector against the tree and
writes `coverage.md` (human report) and `coverage.json` (machine
evidence). It recognises `ast` (`enclosed_by` / `requires_kwarg`) and
`grep` detectors; `manual`/`skill` standards are reported as skipped.

Paste the script's stdout/stderr into your closeout or report. The
summary line names the declared project state, scanned count, total gap
count, and non-passing status counts such as `gated out`,
`language-unsupported`, and `no-files-matched`.

Optional explicit-state form, for replaying a project-state fork:

```bash
"${HOST_PYTHON}" "${SKILL_ROOT}/scripts/scan_coverage.py" \
  --ideas "$STANDARDS" \
  --project-root "$(pwd)" \
  --project-state ".engineering/project-state.json" \
  --output-dir "$REPORT_DIR"
```

### Stage 2 — Summarize

Read `coverage.md` and, when judging status bands, confirm the matching
record in `coverage.json`. Report to the user in ≤10 lines:

- per standard: situation-site count, gap count, coverage %;
- the highest-priority gaps (a security/resilience standard with gaps
  outranks a style one);
- standards that came back **clean** (`status: scanned`, 0 gaps) — name
  them, that is a positive result;
- standards that were `partial` — name their skipped-file count and any
  unsupported-file count/extensions separately; their gaps are triage evidence,
  but the standard is not clean/compliant;
- standards that were `gated_out`, `language_unsupported`,
  `no_files_matched`, `skipped`, or `error` — name them separately and
  do not count them as compliant;
- path to `${REPORT_DIR}/coverage.md`.

### Stage 3 — Hand off

- Genuine gaps on a security/resilience standard → `/fix-workflow` with
  the gap list, or spin off a triage task.
- A standard that is mostly-clean with a couple of gaps → fix inline.
- A standard you keep wanting → add it to the standards file so every
  future run checks it. The standards file is the durable artifact.

## TypeScript/TSX support and limits

TypeScript v1 supports one intentionally narrow structural contract:
`kind: "ast"`, `enclosed_by: "try"`, and a `call_matches` regular expression
against a direct syntactic identifier/property chain. For example, this scans
both `.ts` and `.tsx` source without assuming React or another framework:

```json
{
  "kind": "ast",
  "call_matches": "^JSON\\.parse$",
  "enclosed_by": "try",
  "paths": ["src/**/*.ts", "src/**/*.tsx"]
}
```

The bundled TypeScript Compiler API parser establishes syntax only. It does not resolve aliases, types, receivers, or frameworks beyond that direct spelling.
`JSON.parse` means that literal call spelling, not a proof that it is the global API. A nested
function/callback body resets `try` enclosure because the scanner does not
infer when that callback runs. It ignores `.d.ts`, generated/minified/bundle,
test/spec, fixture, build, dependency, report, and vendor paths even when the
detector directly names them; paths are project-root-relative, and symlinks
escaping the project root are excluded.

`requires_kwarg` and `enclosed_by: "with"` remain Python-only contracts.
TypeScript/TSX standards using either return `language_unsupported`; split a
mixed-language standard into language-specific entries rather than treating an
unsupported condition as a clean scan. Missing Node, missing host-local
`typescript`, or a TypeScript parser preflight failure also returns
`language_unsupported`, never 0 gaps. Mixed Python plus TypeScript/TSX paths
are scanned together only for the shared `enclosed_by: "try"` contract.
A per-file TS syntax/read failure produces `status: partial` with
`skipped_files`; that is never clean/compliant even when its gap count is 0.
When an `ast` path also matches an unsupported extension (for example `.js`),
the scanner still reports findings from supported `.py`/`.ts`/`.tsx` files but
returns `partial` with `unsupported_files` and `unsupported_extensions`.
If no supported files remain, it returns `language_unsupported` instead.

## When the target language or condition isn't supported

When a standard's `paths` cannot be analyzed,
`scan_coverage.py` reports **`language_unsupported`** — *not* as "0 gaps".
**Treat `language_unsupported` as "could not analyze", never as
"compliant".** A silent "0 gaps" on an unanalyzable language is the one
genuinely dangerous failure mode of this skill.

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
| `--ideas` is missing, malformed JSON, or has no `ideas` array | Stop and report the exact script error. Do not synthesize a standard list from prose |
| Explicit `--project-state <path>` does not exist, or a present state file is malformed | Stop and fix the state path/file. Do not fall back to assumed MAX for an explicit typo |
| No project state exists at the default location | Accept the script's assumed-MAX warning, paste it, and tell the user `/orient` can declare the real `(maturity, stakes)` |
| A standard is `gated_out` | Report it as out of scope for the declared project state. It was not scanned and is not a 0-gap pass |
| A standard reports a huge gap count | The detector is too broad, or the situation regex matches non-code — tighten `call_matches`, or switch a `grep` standard to `ast` |
| A `grep` standard flags comments/strings | Expected — `grep` is comment/string-blind. Convert it to an `ast` detector |
| 0 standards fully scanned | Check `coverage.json`: entries may be `partial`, `gated_out`, `manual`/`skill`, `no_files_matched`, or `error`. Report the actual statuses |
| `partial` | Report skipped-file count plus unsupported-file count/extensions when present. Do not call 0 gaps compliant; repair the source, narrow the paths, or extend the scanner and re-run |
| `no_files_matched` | Treat as a misconfigured glob or wrong project root, not as compliance |
| `language_unsupported` | Check the reported reason (unsupported language/condition or missing TS prerequisite), then apply the unsupported branch above |
| A gap is a deliberate exception | Not a tool failure — note it at fix time; a future `--allow` list could record approved exceptions |

## Replay case

For future repairs to this skill, replay a tiny standard against a
temporary project and paste the real stdout plus the first status row from
`coverage.json`. The expected shape is: absent project state prints the
assumed-MAX warning; a Python or supported TypeScript `ast` standard with one
unsatisfied call prints `state production/public-adversarial: scanned 1/1
standard(s): 1 coverage gap(s)`; `coverage.json` records `status: scanned`.

## Census mode — discover before you declare

`scripts/census.py` answers the upstream question: **"for a given *concern*,
what variants exist across a surface, what is the majority, and who are the
stragglers?"** Use it *before* declaring a standard when you do not yet know
which shape to canonicalize.

The workflow:
1. Run census → see variant distribution.
2. Pick the majority variant as the standard (or consciously choose a
   different one and note why in the ADR).
3. Declare the standard in `standards.json` and use `scan_coverage.py` to
   enforce it going forward.

Census output feeds `/decide` — paste the variant table into the ADR context
to record the population state at decision time.

### When to use census vs scan_coverage

| Question | Tool |
|---|---|
| "Is standard X applied everywhere?" | `scan_coverage.py` |
| "What variants exist for concern Y before I decide?" | `census.py` |

### Pipeline

```bash
TS=$(date +%Y%m%d-%H%M%S)
REPORT_DIR="reports/standard-gaps/census-${TS}"
mkdir -p "$REPORT_DIR"

"${HOST_PYTHON}" "${SKILL_ROOT}/scripts/census.py" \
  --concern json_response_envelope \
  --project-root "$(pwd)" \
  app/api \
  --json "${REPORT_DIR}/findings.json"
```

Output: per-variant counts sorted desc, majority variant + share %, straggler
`file:line` list for minority variants, opaque (non-literal payload) count.
The `--json` artifact carries the full structured data for downstream tooling.

### Registered concerns

| Concern ID | What it detects |
|---|---|
| `json_response_envelope` | Django `JsonResponse({...})` dict-literal shapes: sorted top-level keys, `status` kwarg presence, literal status value. Opaque = variable/non-literal payload. |

To add a concern: register a new `Concern(...)` entry in `CONCERN_REGISTRY`
in `census.py` (~30 lines). A concern provides a `site_finder(path, root) →
list[Site]` that returns one `Site` per occurrence with a normalised
`variant` key or `"opaque"`.

## Repository layout

```
.claude/skills/find-standard-gaps/
├── SKILL.md                  # this file — orchestrator
├── scripts/
│   ├── scan_coverage.py      # gap scan — deterministic, stdlib-only
│   ├── project_state.py      # ADR-0020 activation gate helper
│   ├── engineering_home.py   # bundled state-home resolver
│   ├── detect_typescript_calls.mjs  # TS/TSX syntax facts
│   └── census.py             # census mode — discover before you declare
├── knowledge/
│   └── detector-model.md     # the detector model + how to add a standard
└── standards/
    └── standards.example.json  # template — copy to standards.json and adapt
```
