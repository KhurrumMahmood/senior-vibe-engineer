---
name: prevent-regression
description: |
  Turn a closed cleanup cluster into a permanent guardrail: diff-scoped
  lint when the invariant is lexical/AST-shaped, or focused regression
  tests when the invariant is behavioral/contract-shaped. Accepts a
  cluster ID from a recent scan (`cluster:<id>`, `delete:<id>`,
  `semantic:<id>`, `dormant:<id>`), a free-form pattern description with
  optional `path:<glob>` qualifier, a product-topology template
  (`topology:<route-ownership|workflow-registry|frontend-boot|site-endpoints|doc-route-drift>`),
  or `--dogfood <rule-name>` to rewire an existing rule. Emits a proposal
  at `reports/prevent-regression/<id>/` containing the guard artifacts,
  canonical-pattern/testing guidance when needed, and a verification
  recipe. Read-only against production code — never installs the guard
  unilaterally; the human reviews and executes.
argument-hint: "<cluster-id> | topology:<template> | <free-form pattern> | --dogfood <rule-name>"
allowed-tools: Bash, Read, Grep, Glob, Write, Edit, Agent
user-invocable: true
tier: maintenance
job: guard
best_for: |
  Turning a one-off cleanup cluster (just closed by /fix-workflow,
  /unify-shadows, /extract-enum, /introduce-fk, or a topology
  refactor) into a guardrail: either a diff-scoped lint rule + fixture
  + CLAUDE.md canonical-pattern entry, or a focused regression test
  that pins a route/import/auth/CSRF/failure-cleanup contract. Skipping
  GUARD turns every cleanup into a recurring tax — this is the closing
  step of the maintenance loop.
not_for: |
  Detection of new smells (use a find-* SUSPECT skill). Refactor
  execution (use /fix-workflow or /refactor-subsystem). One-off
  pattern fixes the team has decided NOT to enforce broadly (just
  fix in place).
language: python
framework: django
---

# /prevent-regression

You are the **orchestrator** for turning a one-off cleanup into a
permanent guardrail. A cluster that `/fix-workflow` has just closed is
evidence that one shape of bug can recur; this skill emits a
diff-scoped lint rule (plus fixture + CLAUDE.md canonical-pattern
entry) so the same shape cannot land again.

Invocation does **not** authorize rolling the rule out. The skill
produces a **proposal** under `reports/prevent-regression/<id>/` and
stops. The human reviews and executes.

Guard artifacts are **staged, not installed**: author them under the
proposal directory at their repo-relative destination paths
(`reports/prevent-regression/<id>/scripts/lint/<rule>.py`,
`reports/prevent-regression/<id>/tests/lint/<rule>_bad.<ext>`, …), and
emit wiring (pre-commit hook, CI step, `run.py` RuleSpec, CLAUDE.md
bullet) as ready-to-apply diff blocks inside `proposal.md`. The Phase
Pre/Post conditions below name destination paths — read each as "staged
under the proposal directory at that relative path" until the human
installs.

## How success is judged

- Guard artifact + verification recipe **emitted, never installed
  unilaterally** — no guard artifact or wiring edit lands in the
  working tree.
- The skill's own verifier passes and its output is pasted, not
  asserted: `verify_rule.py` reports BAD_RC=1, GOOD_RC=0 (Phase 3).
- Historical fire: the rule fires on each pre-fix site via
  `git show <anchor>^:<file>` and is clean on current HEAD (Phase 6).
- The bad fixture covers every anti-pattern variant and the good
  fixture proves the rule stays quiet on legitimate forms (Phase 3) —
  the precision/recall gates a conformance harness re-runs by
  side-effect.
- Test-only guards (Phase 3b): the focused regression module runs
  green, with its run output in the proposal.

Procedural detail lives beside this file:

- `_common/skill-conventions.md` — shared conventions (symbolic names,
  report shapes). `knowledge/` is a host-overlay slot for custom-lint
  patterns the host project adopts; it ships empty in this ecosystem.
- `agents/rule-designer.md` — scout brief for pattern-shape analysis.
- `scripts/generate_rule.py` / `scripts/verify_rule.py` — helpers.

## Argument parsing

Four forms. Detect and route:

### Form A — Cluster ID from a recent scan
Pattern: `cluster:<id>`, `delete:<id>`, `fix:<id>`, `semantic:<id>`,
`dormant:<id>` — anything `/fix-workflow` accepts.

Load the corresponding triage entry from
`reports/<scan>/latest/report.md` or `triage.md` and extract:

- files touched
- fix shape (e.g. `quasi_dead_broken`, `extract_helper`)
- the git commit(s) that landed the fix (from the learnings log or
  `git log --grep=<id>`)

### Form B — Explicit pattern description
A sentence plus an optional `path:<regex>` qualifier. Example:

> "bare `int(request.POST.get(...))` without `safe_int` in views"
> `path:core/views/**/*.py`

Treat the sentence as the rule intent. Before producing a proposal,
ask for one clarification round if the path scope or anti-pattern AST
shape is ambiguous.

### Form C — `--dogfood <rule-name>`
Used when the rule script already exists under `scripts/lint/` and
you only need to (re)wire it, regenerate fixtures, or refresh the
CLAUDE.md entry. Skip Phase 1 and start at Phase 2.

### Form D — Product-topology guard template
Pattern: `topology:<route-ownership|workflow-registry|frontend-boot|site-endpoints|doc-route-drift>`.

Use this when a workflow cleanup has already landed and the user wants
to prevent drift from returning. The skill should start from the
corresponding product-topology report, not from a raw grep:

- `route-ownership`: block new workflow routes from being added to the
  global root URL file once an include boundary exists.
- `workflow-registry`: block new sidebar/dashboard step definitions
  outside the canonical registry.
- `frontend-boot`: block new template-level `window.*` globals outside
  the canonical boot payload.
- `site-endpoints`: block hardcoded registry-owned
  `/api/sites/<site_id>/...` consumer strings once the workflow boot
  payload exposes endpoint keys.
- `doc-route-drift`: add a scheduled or diff-scoped docs-vs-routes
  check when route docs repeatedly drift.

## Core beliefs

1. **Ruff first; custom rule only when ruff misses.** If the pattern
   maps to a ruff code (e.g. `BLE001` for broad-except), prefer
   enabling it in `pyproject.toml` over a new AST script. A custom
   script should fire where ruff is silent or too broad.
2. **Diff-scoped enforcement.** Pre-commit lints staged files only;
   CI lints `origin/main...HEAD`. Existing violations in untouched
   files never block unrelated work. Anything else is a political
   negotiation we don't want.
3. **Allow-list must require a reason.** Every custom rule supports
   `<comment> noqa: <rule>: <non-empty reason>`. Allow-lists without
   reasons degrade into permanent suppressions.
4. **Fixture pair is load-bearing.** The rule is only trustworthy if
   a `tests/lint/<rule>_bad.<ext>` fires on every anti-pattern variant
   AND a `tests/lint/<rule>_good.<ext>` fires on zero.
   `verify_rule.py` asserts both on every run.
5. **One commit per guard.** The proposal bundles the guard artifacts
   that enforce one invariant. For lint guards, that means rule script,
   fixtures, verification report, pre-commit + CI wiring, and the
   CLAUDE.md Canonical Patterns entry. For test-only guards, that means
   the focused regression test(s), verification recipe, and any
   canonical-pattern text. Splitting one guard across commits makes
   bisect useless when someone tries to revert.
6. **Topology guards wait for a convention.** Do not guard against
   route sprawl or boot globals before the workflow has an accepted
   registry/include/payload shape; otherwise the guard blocks migration
   work instead of protecting it.
7. **Topology guards need positive and negative coverage.** For
   registry, boot-payload, or endpoint-sprawl guards, pair the negative
   static lint with a positive contract test that proves the canonical
   registry/payload still exposes the expected keys or URLs.
8. **Match the language surface.** Python rules can be AST-based. JS,
   template, and docs rules may be lightweight lexical checks when that
   is the narrowest reliable shape. Keep the same CLI contract and
   reason-required allow-list, but use the file suffix and comment style
   of the guarded language.
9. **Prefer canonical derivation over duplicate guard tables.** When a
   guard protects a registry-owned contract, derive expected keys,
   suffixes, or route names from the canonical registry/URL metadata
   where practical. A regression test that copies the whole registry is
   itself a small maintenance smell.
10. **Lint guards and test guards are peers.** Use lint when the
   invariant is a path-scoped lexical/AST shape. Use tests when the
   invariant is behavioral or contract-shaped: import shims stay stable,
   an old flat file must not return, per-endpoint anonymous/user/staff
   and CSRF expectations hold, credential literals stay absent from
   hidden diagnostics/logs/fake defaults, fake production fallbacks stay
   gone, or dispatch failure cleans up domain state.
11. **Detector bands are the third peer.** A band in `find-folder-
   topology-drift` (or a sibling MAP/SUSPECT scanner) belongs
   alongside lints and tests when the rule needs *neighbor context*
   to fire — filename-vs-parent-folder mirroring, sibling-cluster
   thresholds, duplicated subtrees, route-vs-page mirroring. Per-file
   violations stay in lint (commit-time, narrow); cross-file or
   path-shape violations land as a band (audit-time, whole-tree).
   Some invariants earn both: the lint is the primary guardrail; the
   band catches what slips past hooks (direct-to-main pushes, files
   pre-dating the rule, merge commits that bypass the diff scope).
   Default: lint when you can; add a band only when the rule is
   genuinely topological.

## New-Feature Guardrail Prompts

When a new feature establishes a reusable convention, ask whether a
lightweight guard should land with it:

- route or endpoint keys: reverse-backed contract tests may be enough;
  add a lint only if hardcoded consumers are likely to recur.
- template-to-JS boot data: prefer one payload/accessor plus a static
  test that retired globals or raw endpoint strings stay gone.
- status/phase/state fields: prefer `TextChoices` at creation time so
  `stringly-status` never needs a waiver.
- prototype graduation: pair the feature with a dormant sweep or an
  explicit quarantine reason for leftover static/template entry points.
- admin/settings cleanup: prefer endpoint-contract and
  credential-literal tests over a bespoke lint unless the same lexical
  leak appears in multiple files. Staff APIs may legitimately return
  configured sensitive values for editing; the guard is that they are
  never public, unauthenticated, logged, fake-defaulted, or exposed via
  hidden command diagnostics.
- async dispatch conversion: add a broker-failure cleanup test whenever
  `safe_dispatch` replaces inline/thread execution.

## Phase 1 — Pattern discovery

**Pre:** argument resolved.
**Post:** `reports/prevent-regression/<id>/pattern.md` exists with
the rule intent, path scope, file suffixes, and match shape.

Run `git show <commit>` for the fix commit(s). Read the diff. Classify:

- **Ruff-coverable:** the pattern corresponds to an existing ruff rule
  (consult https://docs.astral.sh/ruff/rules/). Emit a
  `pyproject.toml` diff that enables the rule and optionally narrows
  `per-file-ignores`. Skip to Phase 4.
- **Custom rule:** the pattern is narrower, domain-specific, spans a
  non-Python language, or requires looking at source comments (e.g. the
  allow-list shape).
  Proceed to Phase 2.

Record the classification, rule name, path scope, file suffixes, and
anti-pattern shape. For Python, describe the AST shape (what
`ast.walk` looks for). For JS/templates/docs, describe the lexical or
parser shape and the false-positive boundaries. Use symbolic names in
prose — see `_common/skill-conventions.md` "No raw line numbers".

## Phase 2 — Rule script

**Pre:** classified as custom rule.
**Post:** `scripts/lint/<rule>.py` exists and is smoke-tested.

Contract for every custom rule:

- **Stdlib-only.** Runs under bare `python3` (no `.venv` required).
- **CLI:** accepts `<file>` / `<directory>` positionals OR `--stdin
  --filename=<name>`; exit 0 on clean, 1 on violations, 2 on
  invocation error. Directory scans use `scripts/lint/path_utils.py`
  for skip directories and expand only the rule's suffixes.
- **Output:** one line per violation, format
  `<path>:<line>:<col>: <rule>: <message>`.
- **Allow-list:** `<comment> noqa: <rule>: <reason>` on any line of
  the matched span, reason regex `\S` (non-empty). Use `#` for Python
  and `//` for JS.

`silent_catch.py` is the Python reference implementation. For JS
lexical guards (`no_site_endpoint_sprawl.py` was the source host's
exemplar — not shipped in this ecosystem;
<!-- host-adapter: point at a local JS lexical rule exemplar when one exists -->),
keep this shape: suffix expansion, template-literal/string-concat
matching, blockable comments, and a reason-required `// noqa`.

## Phase 3 — Fixtures

**Pre:** rule script works on synthetic input.
**Post:** `tests/lint/<rule>_bad.<ext>` + `tests/lint/<rule>_good.<ext>`
exist and `verify_rule.py` passes.

`<rule>_bad.<ext>` must contain **every variant** of the anti-pattern the
rule is supposed to catch — at minimum one example per branch of the
rule's matcher. `<rule>_good.<ext>` must contain the legitimate
patterns the rule must NOT flag: narrow exceptions, logged paths,
re-raises, allow-listed cases.

Python fixtures carry `# ruff: noqa` at the top so they don't
double-fail the standard ruff pass. Non-Python fixtures use the normal
comment style for explanatory fixture comments.

Run:

```bash
python3 .claude/skills/prevent-regression/scripts/verify_rule.py \
  --rule scripts/lint/<rule>.py \
  --bad tests/lint/<rule>_bad.<ext> \
  --good tests/lint/<rule>_good.<ext>
```

It must report BAD_RC=1 (violations fired) and GOOD_RC=0 (no false
positives). If either is wrong, iterate on the rule or fixtures.

### Phase 3b — Test-only guard

Use this instead of Phases 2–3 when the invariant is best expressed as
a Django/unit test rather than a lint. Examples:

- old module path and parent-package import shims stay importable,
- retired flat implementation file does not return after a package split,
- settings/admin APIs keep their expected anonymous/user/staff response
  contract (for example `401`/`403` on JSON APIs) and staff mutations
  require CSRF,
- known credential literals or raw command snippets are absent from
  templates and hidden diagnostics,
- production fake fallback data is gone while tests inject explicit
  fixtures,
- `safe_dispatch` broker failure marks the owning job failed or
  cleanup-complete.

Write the smallest focused test module that protects the invariant,
derive expected routes/keys from URLconf or canonical registries where
practical, and run that module plus the baseline suite. The proposal
still needs a pattern section, verification results, and follow-on
findings; it simply has no lint script or fixture pair.

## Phase 4 — Wire into pre-commit + CI

**Pre:** `verify_rule.py` passes.
**Post:** `.pre-commit-config.yaml` has a `local` hook entry for the
rule; `.github/workflows/ci.yml` has a diff-scoped step that runs the
rule on the same file set.

Hook shape. Keep pre-commit broad and put the real rule scope in
`scripts/lint/run.py` so local hooks and CI share the same filter:

```yaml
  - repo: local
    hooks:
      - id: <rule>
        name: "<rule> (<short rationale>)"
        entry: python3 scripts/lint/run.py --rule <rule>
        language: system
        types: [python]
        files: '^core/.*\.py$'
```

For non-Python guards, set `types` and `files` to the broad staged-file
surface for that language, and add a `RuleSpec.suffixes` entry in
`scripts/lint/run.py` so `--staged`, `--changed-from`, and explicit
paths all collect the same file types.

CI runs `python3 scripts/lint/run.py --changed-from "$BASE" --rule all`.
When adding a rule, add one `RuleSpec` in the runner; do not duplicate
the scope regex in workflow shell.

## Phase 5 — Canonical Patterns entry

**Pre:** rule wired.
**Post:** `.claude/CLAUDE.md` has a new bullet under "Canonical
Patterns" naming the rule, its intent, and the allow-list shape.

Entry template (one bullet, ≤4 lines):

```markdown
- **`<rule>` / `scripts/lint/<rule>.py`** — <one-line intent>. The
  allow-list is `<comment> noqa: <rule>: <reason>` (reason required).
  See `tests/lint/<rule>_{bad,good}.<ext>` for the canonical examples.
```

Match the existing "Canonical Patterns" list's voice — imperative,
no emoji.

## Phase 6 — Proposal + report

**Pre:** Phases 1–5 complete.
**Post:** `reports/prevent-regression/<id>/proposal.md` written,
`reports/_meta/effectiveness.jsonl` appended, user notified.

`proposal.md` structure:

```markdown
# Rule proposal: <rule>

## Source cluster
<cluster id + commit ref>

## Pattern
<match shape + path scope + rationale>

## Artifacts
- lint guard: scripts/lint/<rule>.py (new),
  tests/lint/<rule>_{bad,good}.<ext> (new),
  .pre-commit-config.yaml (modified),
  .github/workflows/ci.yml (modified),
  .claude/CLAUDE.md (modified — Canonical Patterns entry)
- test-only guard: focused regression test module(s) plus any
  Canonical Patterns / testing-doc entry needed to explain the
  invariant

## Verification
- `verify_rule.py`: BAD_RC=1 with <N> hits, GOOD_RC=0.
- Historical regression: rule fires on
  `git show <anchor>^:<file>` for each pre-fix site.
- Clean on current HEAD: <list files checked>.

## Follow-on findings
<violations surfaced on other in-scope files that this cluster
did NOT fix — these become new /fix-workflow or /find-dormant
candidates, not Phase 1 work>
```

Append to `reports/_meta/effectiveness.jsonl` using the shared
`scripts/log_effectiveness.py`:

```bash
python3 scripts/log_effectiveness.py \
  --skill prevent-regression \
  --scan-id "prevent-regression-${TS}" \
  --target "scripts/lint/<rule>.py" \
  --findings-total N \
  --buckets '{"<rule>": N}' \
  --notes "<optional>"
```

## Step 7 — Summarize

Report to the user in ≤10 lines:

- Rule name + AST shape.
- Files created/modified (1 line each).
- Verification results (pass/fail).
- Follow-on findings count (if any).
- Path to `proposal.md`.
- Next recommended action: human reviews the proposal, installs the
  staged artifacts and wiring diffs, and commits — or abort if
  verification failed.

## Non-goals

- Fixing pre-existing violations on unrelated files — that's
  `/fix-workflow` work, surfaced here as follow-on findings.
- Broadening the rule's AST shape beyond what the source cluster
  demonstrated — two clusters justify one rule, not a family.
- Running full-repo lint — the rule is diff-scoped by design.

## Repository layout

```
.claude/skills/prevent-regression/
├── SKILL.md                         # this file — orchestrator
├── agents/
│   └── rule-designer.md             # pattern-shape scout brief
├── knowledge/                       # host-overlay slot — ships empty;
│                                    # conventions live in _common/skill-conventions.md
└── scripts/
    ├── generate_rule.py             # rule scaffold generator (Phase 2)
    └── verify_rule.py               # fixture-pair verifier (Phase 3)
```
