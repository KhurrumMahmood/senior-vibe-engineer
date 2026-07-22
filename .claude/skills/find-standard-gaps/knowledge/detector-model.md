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

- `enclosed_by`: `try` | `with` | `defer` — the call must be lexically inside
  that block. Enclosure resets at a nested-function boundary (a call in
  a nested `def` is not protected by an outer `try` at runtime). `defer` is
  the Go-only direct-call contract described below; Java supports only `try`.
- `requires_kwarg`: `<name>` — the call must pass that keyword argument
  (a `**kwargs` spread counts — the detector cannot tell, so it assumes
  satisfied rather than false-flag).

A gap = a matched call that fails the condition. `ast` is **preferred**
for every standard about code structure: it is syntactically precise —
it never matches inside a comment or a string literal.

For TypeScript/TSX, v1 supports only `enclosed_by: "try"`. It parses direct
identifier/property-access calls through the host's local TypeScript Compiler
API, so a direct `JSON.parse(value)` can be checked without treating comments
or strings as calls. `requires_kwarg` and `enclosed_by: "with"` are
Python-only and report `language_unsupported` for TS/TSX rather than a false
clean result. The TS scanner does not resolve aliases, types, receivers, or
framework APIs; call-name matching is syntactic. A nested function/callback
resets `try` enclosure because its invocation timing is not established.

For Go, v1 supports only `enclosed_by: "defer"`. A bundled Go 1.22+
standard-library parser records directly spelled identifier, selector,
parenthesized, and generic calls. Only the direct call governed by `defer` is
satisfied; calls used to evaluate its receiver or arguments run immediately
and remain gaps. The scanner does not resolve aliases, types, receivers, or
signatures. Generated/test/vendor/testdata sources are excluded, while syntax
failures and explicit or filename-based build constraints make the result
partial rather than clean.

For Java, v1 supports only `enclosed_by: "try"` with JDK 17+ (`java` and
`javac`) on `PATH`. A family-local public Compiler Tree API helper parses
direct identifier/member-select calls, counts calls in a try resource/body as
enclosed, and resets enclosure for catch/finally, lambda, local-class, and
anonymous-class bodies. It runs neither Maven nor Gradle and resolves no
classpath, imports, aliases, types, overloads, receivers, or framework APIs.
An unresolved name is syntax evidence only. Generated/test/vendor/build-output
and external-symlink paths are excluded; syntax/read failures are partial.

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

## Activation gating

Before any detector runs, `scan_coverage.py` asks whether the standard is
in scope for the project's declared state. The state axes are:

- `maturity`: `prototype` < `first-users` < `production`
- `stakes`: `internal` < `external` < `public-adversarial`

State is loaded from `.engineering/project-state.json`, with the legacy
`.project-state.json` path accepted during the transition. If neither
exists, the scanner assumes the maximum state (`production` /
`public-adversarial`) and prints a warning so production-grade standards
are not silently skipped.

A standard can declare:

- `activation: {"baseline": true}` — always in scope.
- `activation: {"rungs": [{"min_maturity": "production",
  "min_stakes": "external"}]}` — in scope when at least one rung is
  satisfied by the declared state.

When no `activation` block exists, the scanner treats the standard as
baseline for backward compatibility. When a standard is not in scope, the
output status is `gated_out`: the detector did not run, the standard did
not pass, and its gap count must not be read as zero.

## Language support

- The **`ast` detector supports Python plus narrow TypeScript/TSX, Go, and Java syntax**.
  Python retains both `enclosed_by` forms and `requires_kwarg` through
  CPython's standard-library `ast`. TS/TSX supports only `enclosed_by: try`
  through the bundled Compiler API launcher, which requires Node and a
  `typescript` package resolvable from the host `package.json`. Go supports
  only direct `enclosed_by: defer` through a bundled stdlib helper and requires
  Go 1.22+ on `PATH`. Java supports only direct `enclosed_by: try` through a
  public JDK Compiler Tree API helper and requires JDK 17+ on `PATH`.
- The **`grep` detector is cross-language** (it operates on text) — but
  comment/string-blind, so trust it for *enumerating* situations, not
  for deciding satisfaction.
- When an `ast` standard matches both supported Python/TS/TSX/Go/Java files and an
  unsupported extension, `scan_coverage.py` retains the supported findings but
  reports `partial`, with `unsupported_files` and
  `unsupported_extensions`; it is never a false "0 gaps" pass. When no
  supported files remain, when a language-unsupported condition is used, or
  when the required TypeScript, Go, or JDK preflight cannot run, it reports
  `language_unsupported`. The orchestrator
  then applies the **"When the target language or condition isn't supported"**
  rule in `SKILL.md`: small surface → read it directly; large surface → build
  the detector tooling first.
- Further language support remains a scoped adapter decision. Do not assume a
  universal parser or node schema: satisfaction vocabulary is language-
  specific (`requires_kwarg` is meaningless in Go/Java and `enclosed_by: try`
  is meaningless in Go/Rust). Prefer the smallest native fact that proves one
  useful standard contract.

## Scoping `paths`, and reading the count honestly

Lessons from a dogfood run of the shipped `standards.example.json` against
a real host project (2026-05-21):

- **Scope `paths` to first-party source roots, not `**/*.py`.** Every
  detector that used the whole-tree glob (`**/*.py`) was swamped: ~90% of
  its hits were a stale agent worktree (now skipped) plus vendored
  reference code, test harnesses, and one-off scripts. The single detector
  that stayed clean — `idea-no-print-in-service-code` — was the only one
  whose `paths` were already source-rooted (`["app/**/*.py", "src/**/*.py",
  "services/**/*.py"]`). A `**/*.py` glob requires the path to *start* at
  the repo root, so a source-rooted glob like `app/**/*.py` never matches
  `<anything>/app/...` copies. **Narrow `paths` per project**; the shipped
  example is a starting point, not a finished config.
- **Paths are project-root-relative and exclusions cannot be bypassed by a
  direct target.** The scanner excludes generic test/dependency/worktree trees
  for every language. Its TS/TSX branch additionally excludes declaration,
  generated, minified/bundle, test/spec, fixture, build, report, and vendor
  source. A `paths` entry can be a root-relative file, directory, or glob; an
  external symlink is never first-party source. If a standard names only
  excluded paths, it returns `no_files_matched` rather than scanning an
  out-of-policy copy.
- **A pure-prohibition count is presence, not severity.** The floor
  reported 21 `eval`/`exec` sites; a hand audit of the same project found
  **8** that were the actual remote-code-execution risk (LLM-generated code
  reachable from an unauthenticated endpoint). The other 13 were docstrings
  *about* `exec`, vendored code, and test harnesses. The floor's job is
  "go look here"; deciding *which* matches are dangerous and *why* is the
  `manual`-ceiling / reviewer's job. Never report a pure-prohibition gap
  count as a bug count.
- **`grep` over-counts via comment-blindness — confirmed in the wild.** Of
  those 21 `eval`/`exec` hits, 3 were comment/docstring lines mentioning
  `exec`, and a `verify=False` hit was an explanatory comment. This is the
  documented `grep` weakness, not a surprise — it is why the count is a
  triage queue, not a verdict.
- **An inert suppression is a gestured-at control, not a real one.** The
  host project carried `# noqa: S102` (Bandit "exec used") comments while
  `S` was *not* in its ruff `select` list — suppressing a rule that never
  ran. The floor is blind to `# noqa`; a reviewer reads the justification
  and judges whether the suppression is earned. Treat suppression presence
  as a signal to check, not as satisfaction.

## Honest limits

- A `situation` / `call_matches` pattern cannot capture judgment-heavy
  standards. Those stay `manual`. Not every standard is mechanically
  detectable — and that is fine.
- A flagged gap is high-confidence "the standard is not applied here";
  it is **not** a verdict that the gap is a *bug*. Some gaps are
  deliberate exceptions. Triage — genuine / intentional / out-of-scope —
  is a fix-time decision, not the scan's job.
- The scan **never** descends into `tests/`, `migrations/`,
  `experiments/`, `worktrees/`, `.venv/`, or other vendored directories
  (a fixed skip-list in `scan_coverage.py`). `worktrees` is on the list
  because agent worktrees (`.claude/worktrees/<name>/`) are *full repo
  checkouts* — a single stale one double-counts the whole tree (a dogfood
  run inflated every `**/*.py` detector ~10x). A standard whose situation
  lives in a skipped directory — e.g. "tests that open a DB connection
  guard it" — cannot be checked by this skill today; that needs a
  configurable include-list.
- TypeScript v1 does not resolve imports, aliases, overloads, type identity,
  receiver identity, runtime globals, or framework conventions. It is a direct
  syntax detector, not a TypeScript linter or semantic API audit.
- Java v1 does not resolve imports, aliases, overloads, type identity, receiver
  identity, or framework conventions. It is a direct syntax detector, not a
  Java compiler/build or semantic API audit.
- `scan_coverage.py` reports a per-standard status. **Only `scanned` is
  a clean coverage result.** `partial` means one or more files were not read,
  parsed, or had an unsupported extension; its gaps are triage evidence, not a
  compliance verdict. `unsupported_files` and `unsupported_extensions` make
  that unexamined surface explicit when supported findings are still reported.
  `gated_out` (activation thresholds not met), `no_files_matched` (a
  misconfigured glob), `language_unsupported`, and `error` all mean
  part or all of the surface went unexamined — never read them as "0 gaps =
  compliant". A clean result needs `status: scanned` and 0 gaps.
