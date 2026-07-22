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
language: any
framework: any
install_with: [find-implicit-state]
---

# /prevent-regression

You are the **orchestrator** for turning a closed cleanup into a permanent
guardrail. Invocation only stages a proposal below
`reports/prevent-regression/<id>/`; it never authorizes rollout. Stage rule,
fixture, and ready-to-apply wiring at their repo-relative destination paths,
then let the human install or discard them.

## How success is judged

- Emit, never install, the artifact and verification recipe.
- Paste the real verifier result: BAD_RC=1 and GOOD_RC=0 for lint guards, or
  focused test output for behavioral guards.
- Prove the historical fire and current clean result; fixtures cover every
  matched anti-pattern plus legitimate forms.
- Use `_common/skill-conventions.md`, `agents/rule-designer.md`, and the
  bundled generation/verifier helpers for the shared report shape.

## Closed-state guard

For the reviewed first-party `status` / `phase` / `state` path, use the
bundled guard directly after installation:

```bash
python3 scripts/stringly_status_guard.py <file-or-directory>
```

It blocks a bare string Django field, comparison, or assignment and accepts
only a reasoned `# noqa: stringly-status: <reason>` vendor boundary. This is a
family-local reference guard; it does not generate or install unrelated
general-purpose rules.

### TypeScript closed-state guard

Stage—not install—the family-local Compiler API guard for a reviewed closed
TypeScript field. It covers direct/reversed comparisons, one-hop const aliases,
plain/`??=`/chained assignments, and transparent parentheses. A pinned host
TypeScript package plus tsconfig are required; unsupported general dataflow,
ORM behavior, and root lint wiring remain out of scope.

    ID="typescript-state"
    OUT="reports/prevent-regression/$ID"
    node .claude/skills/prevent-regression/scripts/generate_typescript_state_guard.mjs \
      --id "$ID" \
      --project-root "$(pwd)" \
      --tsconfig "$(pwd)/tsconfig.json" \
      --output-root "$OUT"

    node .claude/skills/prevent-regression/scripts/verify_typescript_state_guard.mjs \
      --rule "$OUT/scripts/lint/no_stringly_state.mjs" \
      --bad "$OUT/tests/lint/no_stringly_state_bad.ts" \
      --bad-tsx "$OUT/tests/lint/no_stringly_state_bad.tsx" \
      --good "$OUT/tests/lint/no_stringly_state_good.ts" \
      --good-tsx "$OUT/tests/lint/no_stringly_state_good.tsx"

The report stages guard, TS/TSX fixture pairs, and `host-wiring.diff`; paste
BAD_RC=1/GOOD_RC=0. A reasoned noqa only suppresses a Compiler-resolved vendor
receiver, never a filename or forged first-party comment. The serial integrator
owns staged wiring.

### Checked-JavaScript closed-state guard

Retain complete checked-JavaScript detector evidence and manifest first. The
generator accepts only at least one proven first-party operation from an
`allowJs` + `checkJs` host Compiler API run; partial/unsupported evidence exits
2 rather than fabricating findings.

    ID="javascript-state"
    OUT="reports/prevent-regression/$ID"
    node .claude/skills/prevent-regression/scripts/generate_javascript_state_guard.mjs \
      --id "$ID" \
      --project-root "$(pwd)" \
      --config "$(pwd)/jsconfig.json" \
      --findings reports/implicit-state/findings.jsonl \
      --manifest reports/implicit-state/manifest.json \
      --output-root "$OUT"

    node .claude/skills/prevent-regression/scripts/verify_javascript_state_guard.mjs \
      --rule "$OUT/scripts/lint/no_stringly_state_javascript.mjs" \
      --bad "$OUT/tests/lint/no_stringly_state_bad.js" \
      --bad "$OUT/tests/lint/no_stringly_state_bad.jsx" \
      --bad "$OUT/tests/lint/no_stringly_state_bad.mjs" \
      --bad "$OUT/tests/lint/no_stringly_state_bad.cjs" \
      --good "$OUT/tests/lint/no_stringly_state_good.js" \
      --good "$OUT/tests/lint/no_stringly_state_good.jsx" \
      --good "$OUT/tests/lint/no_stringly_state_good.mjs" \
      --good "$OUT/tests/lint/no_stringly_state_good.cjs"

The proposal stages four fixture pairs and wiring; paste BAD_RC=1/GOOD_RC=0.
Coverage is direct/reversed comparison, assignment, and one-hop const aliases
on JSDoc-closed fields; vendor noqa requires Compiler API evidence. The serial
integrator owns installation.

### Go closed-state guard

After a human accepts a Go proposal, read and follow `knowledge/go-state.md`.
Load that file only for Go work. Never weaken an unavailable semantic closure
to a field-name regex.

### Java 17 exact-authority guard

After a human accepts a Java enum proposal, stage—not install—a guard from its
`targets.json`. It copies the accepted qualified owner, field, source
fingerprint, and family-local JDK compiler helper. The staged rule checks only
that compiler-resolved direct `String` field; it does not broadly match every
field named `state`, `status`, or `phase`. It catches bare assignments,
`String.equals`/`Objects.equals`, and unsafe `==`/`!=` while that exact field
is still `String`.

```bash
OUT="reports/prevent-regression/java-job-status"
python3 .claude/skills/prevent-regression/scripts/generate_java_state_guard.py \
  --targets reports/extract-enum/java-job-status/targets.json \
  --project-root "$(pwd)" --output-root "$OUT"
RULE="$(find "$OUT/scripts/lint" -maxdepth 1 -name 'no_stringly_state.py' -print -quit)"
python3 .claude/skills/prevent-regression/scripts/verify_java_state_guard.py \
  --rule "$RULE" --authority "$OUT/authority.json" \
  --bad "$OUT/tests/lint/bad/Job.java" --good "$OUT/tests/lint/good/Job.java" \
  --project-root "$(pwd)"
```

Install `find-implicit-state` alongside this skill so the generator can copy
its helper; a missing helper or JDK 17 exits 2 rather than falling back to a
name regex. The verifier pastes BAD_RC=1, GOOD_RC=0 and compiles both fixtures
with `javac --release 17 -proc:none`. This branch modifies only the staged
proposal directory, never host guard files; a human integrator owns any later
installation, native check, and rollback.

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

1. **Ruff first.** Use a custom rule only where Ruff is silent or too broad.
2. **Diff-scope and reasoned escapes.** Hooks inspect changed files; custom
   noqa markers require a non-empty reason.
3. **Fixture truth.** Every matcher branch fires in bad fixtures and stays
   quiet in good fixtures; the verifier is the proof.
4. **One invariant, one commit.** Bundle rule/test, fixtures, verifier, and
   staged wiring so a revert and bisect remain meaningful.
5. **Choose the right peer.** Use lint for local shape, tests for behavioral
   contracts, and audit bands only when neighbor/path context is essential.
6. **Protect an accepted convention.** Derive registry facts where possible;
   do not guard topology before its canonical shape exists.

## New-Feature Guardrail Prompts

When a feature establishes a reusable convention, ask whether a lightweight
guard belongs with it: reverse-backed route tests before endpoint lints; one
boot payload plus a retired-global check; typed state authority from creation;
a dormant sweep or quarantine for prototype remnants; endpoint/credential
tests before bespoke lints; and broker-failure cleanup tests for safe dispatch.

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

Use this when a focused test expresses the invariant better than a lint:
import-path stability, retired files, endpoint/auth/CSRF contracts, credential
absence, removed fake fallbacks, or dispatch cleanup. Write the smallest test,
derive canonical routes/keys where practical, run it plus baseline, and retain
the proposal's pattern, verification, and follow-on sections.

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
