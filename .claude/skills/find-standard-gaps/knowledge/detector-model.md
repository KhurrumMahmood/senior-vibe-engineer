# The detector model

How a standard's `detector` is executed by `scan_coverage.py` to find
**coverage gaps** — sites where the standard should apply but doesn't.

## A standard

A standard is one entry in the standards file's `ideas` array:

```json
{
  "id": "idea-<kebab>",
  "label": "short human label",
  "statement": "the rule, in one sentence",
  "contract": {
    "solves": ["the problem this standard prevents"],
    "improves": ["what it makes better"],
    "applies_when": "the situation that triggers the standard",
    "detector": { ... }
  }
}
```

`solves` / `improves` / `applies_when` are the human contract. The
`detector` is the executable part.

## Gap-enumeration

A detector is **lint-shaped**: it finds a *situation* site and reports
it as a **gap** when the standard's satisfaction condition is absent. A
gap = "the situation is here, the standard is not." The scan output is
the gap list directly — no second step.

## The `ast` detector — preferred

```json
"detector": {
  "kind": "ast",
  "call_matches": "<regex on a call's dotted name>",
  "enclosed_by": "try",
  "paths": ["app/**/*.py"]
}
```

Finds `Call` nodes whose dotted name (e.g. `mysql.connector.connect`)
matches `call_matches`, then checks **one** satisfaction condition:

- `enclosed_by`: `try` | `with` — the call must be lexically inside
  that block. Enclosure resets at a nested-function boundary (a call in
  a nested `def` is not protected by an outer `try` at runtime).
- `requires_kwarg`: `<name>` — the call must pass that keyword argument
  (a `**kwargs` spread counts — the detector cannot tell, so it assumes
  satisfied rather than false-flag).

A gap = a matched call that fails the condition. `ast` is **preferred**
for every standard about code structure: it is syntactically precise —
it never matches inside a comment or a string literal.

## The `grep` detector — fallback only

```json
"detector": {
  "kind": "grep",
  "situation": "<regex>",
  "satisfied_by": "<regex>",
  "paths": ["app/**/*.py"],
  "scope": "window",
  "window": 20
}
```

A `situation` regex match is a gap unless `satisfied_by` appears in
scope (`window`: ±`window` lines; `file`: anywhere in the file). Omit
`satisfied_by` for a pure-prohibition standard (every situation match is
then a gap).

**`grep` is false-positive-prone** — it matches inside comments and
string literals with no awareness they are not code, and `scope: window`
is a line-distance heuristic, not real block scope. Reserve `grep` for
genuinely lexical patterns where comment/string matches are absent or
harmless. For anything structural, use `ast`.

## `skill` and `manual`

- `kind: skill` — `ref` names an existing `find-*` skill whose findings
  would be the gap list. Recognised; not implemented yet.
- `kind: manual` — no executable detector; the standard is checked by
  hand. `scan_coverage.py` skips it.

## Language support

- The **`ast` detector is Python-only** — it is CPython's standard-
  library `ast` module. It parses `.py` files; it cannot analyze
  JavaScript, Go, Java, etc.
- The **`grep` detector is cross-language** (it operates on text) — but
  comment/string-blind, so trust it for *enumerating* situations, not
  for deciding satisfaction.
- When an `ast` standard's `paths` match files but none are `.py`,
  `scan_coverage.py` reports it `language_unsupported` — never a false
  "0 gaps". The orchestrator then applies the **"When the target
  language isn't supported"** rule in `SKILL.md`: small surface → read
  it directly; large surface → build the detector tooling first.
- The cross-language path is **tree-sitter** — one parsing library with
  grammars for most languages and a uniform query API. It is a genuine
  rebuild, not a free generalization: it adds a third-party dependency
  (the skill is currently stdlib-only), node-type names differ per
  grammar, and the satisfaction vocabulary is partly language-specific
  (`requires_kwarg` is meaningless in Go/Java; `enclosed_by: try` is
  meaningless in Go/Rust). Treat cross-language coverage as a scoped
  project, not an incremental tweak.

## Honest limits

- A `situation` / `call_matches` pattern cannot capture judgment-heavy
  standards. Those stay `manual`. Not every standard is mechanically
  detectable — and that is fine.
- A flagged gap is high-confidence "the standard is not applied here";
  it is **not** a verdict that the gap is a *bug*. Some gaps are
  deliberate exceptions. Triage — genuine / intentional / out-of-scope —
  is a fix-time decision, not the scan's job.
- The scan **never** descends into `tests/`, `migrations/`,
  `experiments/`, `.venv/`, or other vendored directories (a fixed
  skip-list in `scan_coverage.py`). A standard whose situation lives in
  one of those — e.g. "tests that open a DB connection guard it" —
  cannot be checked by this skill today; that needs a configurable
  include-list.
- `scan_coverage.py` reports a per-standard status. **Only `scanned` is
  a real result.** `no_files_matched` (a misconfigured glob),
  `language_unsupported`, and a `scanned` result with `skipped_files > 0`
  all mean part or all of the surface went unexamined — never read them
  as "0 gaps = compliant".
