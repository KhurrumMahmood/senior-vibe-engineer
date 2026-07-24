---
name: extract-enum
description: Turn a confirmed Django string-state field into a TextChoices proposal, a reviewed TypeScript or checked-JavaScript result into an as-const value-object proposal, or accepted Go, Java 17, Kotlin/JVM, PHP, Ruby, bounded Rust, or bounded Dart implicit-state evidence into a typed-constant/enum proposal. Emits a caller and boundary inventory without editing production code.
argument-hint: "<implicit-state:ID or FILE::FIELD>"
allowed-tools: Bash, Read, Grep, Glob, Write, Edit, Agent
user-invocable: true
tier: maintenance
job: explain
best_for: |
  A confirmed Django model implicit-state target ready for a TextChoices class,
  caller table, data-migration risk review, and stop condition. Decided in:
  0001 (TextChoices for state).
  For TypeScript or checked JavaScript, consume a closed-state detector JSONL
  record and design its exported as-const runtime value object, derived union,
  caller changes, and named vendor boundaries.
  For Go, consume go/types-resolved repeated-operation evidence for a named
  string type plus typed constants.
  For Java, consume exactly one complete JDK-resolved direct String field
  finding for an enum migration with caller-impact review.
not_for: |
  Fresh candidate discovery belongs to /find-implicit-state. Tuple-inferred
  identity expressed through `.filter(..., *_at__...).first()` belongs to
  /introduce-fk, while production refactoring belongs to /fix-workflow.
  Plain first-party sentinels outside a Django model require a separately
  reviewed Python typed-value conversion because the Django collector walks
  model fields. The TypeScript and checked-JavaScript branch excludes
  open-ended values, ORM-specific representations, and existing project-native
  enumerations whose convention lacks fixture evidence.
language: any
framework: any
scans: [python, typescript, javascript, go, java, kotlin, csharp, php, ruby, rust, dart, c, cpp]
install_with: [find-implicit-state, map-subsystem]
---

# /extract-enum

## Swift 6.3.3 accepted enum proposal

Use `scripts/collect_swift_state.py` only with one complete, current
`swift-semantic-facts-v1` pack, its accepted `swift-implicit-state-v1`
finding, and hash-bound human authority. Keep sibling
`_swift-semantic-readonly`; the downstream validator checks accepted evidence
but never recollects compiler facts. The result is read-only and may reuse an
existing String-backed enum. Domain closure, raw values, Codable behavior,
Objective-C/dynamic identity, protocol dispatch, frameworks/Xcode, external
callers, generated/macros/plugins, conditional variants, and compatibility
remain explicit human gates.

## C# accepted enum proposal

Use `scripts/collect_csharp_state.py` only for one fresh, content-addressed
reviewer acceptance produced from the sibling `_csharp-semantic` provider and
`find-implicit-state` C# finding. Read `knowledge/csharp-v1.md` for the exact
command and boundary verdicts. The result is a read-only enum proposal; it
does not prove a closed domain or authorize source mutation. Serialization,
reflection, generated code, frameworks, external callers, and binary
compatibility remain human-owned.

## Kotlin/JVM 2.4.10 proposal

Trigger this branch only from fresh pinned semantic facts, one exact
`find-implicit-state` candidate, and content-addressed human acceptance. Keep
sibling `_kotlin-semantic`, read
[`../_kotlin-semantic/GUIDE.md`](../_kotlin-semantic/GUIDE.md), and enter through
`scripts/collect_kotlin_state.py`. It emits one read-only, wire-preserving enum
proposal; it does not mutate source. The deprecated K1 authority, reflection,
delegation, generated/KAPT/KSP and plugin sources, Gradle variants,
Java/framework/external callers, serialization, JVM ABI, and release safety
remain explicit human gates.

## C++20 branch

Use `scripts/collect_cpp_state.py` with accepted `cpp-semantic-facts-v1` and
`cpp-implicit-state-v1` artifacts; run it with `--help` for the exact CLI. The
content-addressed proposal targets one exact namespace-qualified field and is
proved only in a disposable copy under the same complete C++20 compile
database. Closed-domain, ODR, ABI, specialization, dispatch, external-variant,
and host-mutation authority remain human-owned.

## C17 branch

Use `scripts/collect_c_state.py` on accepted `c-semantic-facts-v1` and
`c-implicit-state-v1` artifacts; run `python3 scripts/collect_c_state.py
--help` for the exact CLI. It emits a read-only proposal for one reviewed
field. Observed literals do not prove a closed domain, ABI/layout, wire or
storage compatibility, external-consumer safety, or mutation authority.

## PHP and Ruby

For accepted PHP evidence, read `_php-proposal/GUIDE.md`. For accepted Ruby
RBS evidence, read `_ruby-semantic/PROPOSAL-GUIDE.md`. Both branches are
proposal-only and require current hash-bound human authority.

## Dart v1

Consume exactly one content-addressed, human-accepted D5 state candidate.
Emit an exact enum/wire-value proposal and validate its six-edit after-tree in
a disposable copy; never edit the audited source.

```bash
SKILL_ROOT=".agents/skills/on-demand/extract-enum"
python3 "${SKILL_ROOT}/scripts/collect_dart_state.py" \
  --project-root "$PWD" --evidence-dir reports/implicit-state/dart \
  --acceptance reports/implicit-state/dart/acceptance.json \
  --output-dir "$PWD/reports/extract-enum/dart"
```

Open domains, stale or unaccepted evidence, generated/private/external owners,
and unresolved wire/public compatibility stop without a proposal.

## Rust v1

Consume exactly one complete `rust-implicit-state-v1` candidate. Verify its
source hashes and exact callers, then emit `targets.json` and a
`review_required` proposal. Never edit Rust source or apply the enum.

```bash
SKILL_ROOT=".agents/skills/on-demand/extract-enum"
python3 "${SKILL_ROOT}/scripts/collect_rust_state.py" \
  --findings "$PWD/reports/implicit-state/rust/findings.json" \
  --project-root "$PWD" \
  --output "$PWD/reports/extract-enum/rust/targets.json" \
  --proposal "$PWD/reports/extract-enum/rust/proposal.md"
```

Fresh upstream evidence requires the accepted `find-implicit-state` and
`map-subsystem` closure; copied execution from accepted findings is standalone.

You are the **orchestrator** for turning a stringly-typed state field
into an implementation-ready `models.TextChoices` proposal.
`/find-implicit-state` already flagged the target; your job is to read
the literals in full, dispatch a scout to profile case-variants /
dynamic-value confusions / caller migration shape, and consolidate into
a proposal the human reviews before handing off to `/fix-workflow` or
`/refactor-subsystem`.

You do NOT write production code in this skill. You never edit the
model file, the callers, or a migration file. The only artifact you
produce is `reports/extract-enum/<target-slug>/proposal.md` plus its
supporting `targets.json` and `profile.md`.

## How success is judged

- `proposal.md` is complete per the Stage 3 structure: a
  `models.TextChoices` class (never tuple-style choices), the caller
  table from `profile.md`, data-migration risks (case-variants,
  third-party bridges), test matrix, and stop condition.
- Form A pasted output shows the exact finding gate: optional
  `implicit-state:` prefix stripped, `recommendation_hint`/`bucket`
  checked as `extract_enum_candidate`, then `collect.py` output
  pasted with literal and caller counts.
- Exactly one target per run — extra stringly-typed fields land under
  Follow-on findings, not in this proposal.
- No file outside `reports/extract-enum/<target-slug>/` was touched;
  execution is deferred to `/fix-workflow` or `/refactor-subsystem`
  after human review.
Write toward these gates from Stage 0.

## TypeScript and checked-JavaScript closed-state branch

Consume detector JSONL; do not infer TypeScript or JavaScript candidates with
a regex or accept a Django finding ID. Checked JavaScript accepts only named
checked-config records. One closed first-party field/type becomes one exported
`as const` runtime value object and derived union; migrate its callers while
preserving named vendor-wire literals. This excludes Django migrations, tuple
identity, ORM conventions, generic enum preference, and unproven native enums.

    STATE_LANGUAGE="${STATE_LANGUAGE:-typescript}" # typescript | javascript
    STATE_MANIFEST="${STATE_MANIFEST:-/dev/null}" # JavaScript: detector manifest (required)
    REPORT_DIR="reports/extract-enum/${STATE_LANGUAGE}-state"
    mkdir -p "$REPORT_DIR"
    node .claude/skills/extract-enum/scripts/collect_typescript_state.mjs \
      --findings reports/implicit-state/<scan>/findings.jsonl \
      --project-root "$(pwd)" \
      --language "${STATE_LANGUAGE}" \
      --manifest "${STATE_MANIFEST}" \
      --output "$REPORT_DIR/targets.json" \
      --proposal "$REPORT_DIR/proposal.md"

For JavaScript, the detector manifest is required and must report a complete
checked-JavaScript run (`allowJs` + `checkJs`) with finite JSDoc authority;
partial, missing-JSDoc, and open/untyped evidence exits 2 before an artifact
exists. The command exits 2 if the detector result is malformed, empty, or mixes
multiple state fields/types. Grade success from targets.json, proposal.md,
and [collect_typescript_state] stderr: the proposal must enumerate every
first-party caller, all distinct literals, and the excluded vendor boundary.
After human review applies the proposal, run the host's npm run typecheck and
native npm test; this skill remains read-only.

## Go typed-state proposal branch

For a Go detector artifact, read and follow `knowledge/go-v1.md`. Load that
file only for Go work. The output is always `review_required`; repeated
literals do not prove a closed domain.

## Java 17 accepted-finding branch

Consume one complete, `status: accepted`,
`bucket: extract_enum_candidate` record from the final Java
`findings.json`. Never re-scan Java source or accept an
`unsafe_string_comparison`; `==` is a correctness finding, not enum proof.
The collector verifies the upstream SHA-256 manifest for the declaration and
every cited caller before writing only `targets.json` and `proposal.md` below
`reports/extract-enum/`.

<!-- installed-command:java-state-proposal:start -->
```bash
JAVA_SCAN="${JAVA_SCAN:-java-state}"
JAVA_FINDING="${JAVA_FINDING:-java-implicit-state-0001}"
REPORT_DIR="${REPORT_DIR:-reports/extract-enum/java-job-status}"
SKILL_ROOT=""
for SKILL_CANDIDATE in \
  ".agents/skills/on-demand/extract-enum" \
  ".agents/skills/extract-enum" \
  ".claude/skills/extract-enum"
do
  if [ -f "${SKILL_CANDIDATE}/SKILL.md" ]; then
    SKILL_ROOT="$(cd "${SKILL_CANDIDATE}" && pwd)"
    break
  fi
done
if [ -z "${SKILL_ROOT}" ]; then
  printf '%s\n' "extract-enum is not installed in .agents/skills/on-demand, .agents/skills, or .claude/skills" >&2
  exit 2
fi
python3 "${SKILL_ROOT}/scripts/collect_java_state.py" \
  --finding "${JAVA_FINDING}" \
  --findings "reports/implicit-state/${JAVA_SCAN}/findings.json" \
  --project-root "$(pwd)" --output "$REPORT_DIR/targets.json" \
  --proposal "$REPORT_DIR/proposal.md"
```
<!-- installed-command:java-state-proposal:end -->

Review the proposed enum's persisted/wire values, serializer/ORM/reflection
boundaries, exact caller table, and native `javac --release 17 -proc:none`
verification before mutation. Stop if the domain is not intentionally finite.
After approval, `/prevent-regression` consumes the saved exact authority; this
skill never installs a guard or edits Java.

## Core beliefs

1. **For a model field, the endpoint is `models.TextChoices`, not a
   tuple-style `STATUS_CHOICES` list.** The `stringly-status` lint rule rejects
   tuple-style choices as "still the smell" — see the CLAUDE.md
   Canonical Pattern entry and `scripts/lint/no_stringly_typed_status.py`.
   Your proposal must propose a `TextChoices` class, not a tuple.
2. **Case-variants and third-party bridges are load-bearing.** An
   accidental `"Pending"` among mostly-`"pending"` rows is a data-
   migration risk, not a noise literal. A vendor-supplied literal
   from a webhook payload is NOT a candidate for an enum member.
   The scout classifies; the orchestrator includes both shapes in
   the risk section.
3. **One target per run.** If the scout surfaces another stringly-
   typed field in the same file, log it under follow-on findings and
   stop. Running `/extract-enum` twice is cheaper than getting one
   proposal wrong.
4. **The proposal is read-only.** No code edits, no migrations, no
   test edits. `/fix-workflow` owns execution.
5. **New fields use a named authority from the first commit.** Model fields use
   `TextChoices`; non-model Python carriers use a nearby str-valued Enum. This
   collector remains model-only, so convert other carriers by hand and do not
   add more callers to legacy tuple-style choices without an explicit follow-up.

## Scope

- **Project root:** this worktree. Source-tree Python uses `.venv/bin/python`;
  copied collectors use stock `python3`/`node` and never import Django or touch
  the DB. This skill is read-only; `/fix-workflow` owns execution. The scout's
  project-specific defaults remain in `knowledge/risk-context.md`.

## Argument parsing

Two forms:

### Form A — Finding ID from /find-implicit-state

Pattern: `implicit-state:<id>` or `<id>` where `<id>` matches
`implicit-state-NNNN`. Resolves against
`reports/implicit-state/latest/findings.json`.

Before calling `collect.py`, strip the optional `implicit-state:`
prefix and check the candidate's `recommendation_hint` or final scout
`bucket`. Only `extract_enum_candidate` may proceed. For
`introduce_fk_candidate`, abort and recommend `/introduce-fk`; for
`enum_already_used`, `legacy_allow_list`, or any other value, abort and
report that the candidate is not an enum-extraction target.

```bash
RAW_FINDING="<implicit-state-id-or-prefixed-id>"
FINDING_ID="${RAW_FINDING#implicit-state:}"
.venv/bin/python -c '
import json, sys
from pathlib import Path
finding_id = sys.argv[1]
path = Path("reports/implicit-state/latest/findings.json")
payload = json.loads(path.read_text(encoding="utf-8"))
records = payload.get("findings") or payload.get("candidates") or []
for record in records:
    if record.get("candidate_id") == finding_id or record.get("id") == finding_id:
        hint = record.get("recommendation_hint") or record.get("bucket")
        print(json.dumps({"candidate_id": finding_id, "hint": hint}))
        if hint != "extract_enum_candidate":
            raise SystemExit(f"not an extract_enum_candidate: {hint}")
        break
else:
    raise SystemExit(f"finding not found: {finding_id}")
' "${FINDING_ID}"
```

If the findings file is missing, abort and tell the user to run
`/find-implicit-state` first — do NOT fall back to scanning.

### Form B — Explicit `<file>::<field>` target

Pattern: `core/models/crawl_jobs.py::status`. The field lives on a
`models.Model` subclass; the skill inspects every comparison/
assignment site in the codebase. An optional third part narrows to a
specific class in files with multiple models:
`core/models/crawl_jobs.py::status::UrlCrawlJob`.

Present the parsed spec back to the user (`target_slug`,
`model_class`, `field_file`) and wait for approval (same approval-
token contract as `/fix-workflow`: first non-whitespace token must be
`approved`, `approve`, `go`, `lgtm`, `proceed`, `yes`). This is the
only interactive step before Stage 0.

## Pipeline

### Stage 0 — Setup

**Pre:** argument parsed, approval received (Form B only). **Post:**
`${REPORT_DIR}` exists, `latest` symlink.

```bash
TARGET_SLUG="<model>__<field>"    # crawljob__status, urlcrawljob__status, ...
REPORT_DIR="reports/extract-enum/${TARGET_SLUG}"
mkdir -p "${REPORT_DIR}"
ln -sfn "${TARGET_SLUG}" reports/extract-enum/latest
```

`reports/extract-enum/` uses target slugs directly (not timestamps) so
successive runs against the same field overwrite. The proposal shape
is deterministic per field.

### Stage 1 — Collect literals + callers

**Pre:** argument parsed. **Post:** `${REPORT_DIR}/targets.json`
with field declaration + literals + comparison/assignment sites.

**Form A:**

```bash
.venv/bin/python .claude/skills/extract-enum/scripts/collect.py \
  --from-finding "${FINDING_ID}" \
  --findings reports/implicit-state/latest/findings.json \
  --project-root "$(pwd)" \
  --output "${REPORT_DIR}/targets.json"
```

**Form B:**

```bash
.venv/bin/python .claude/skills/extract-enum/scripts/collect.py \
  --target "${FILE}::${FIELD}" \
  ${MODEL_CLASS:+--model-class "${MODEL_CLASS}"} \
  --project-root "$(pwd)" \
  --output "${REPORT_DIR}/targets.json"
```

The collector writes to stderr a one-line summary:
`<Model>.<field> — N literals (M case-variants) across K files`. If
zero literals surface, exit 1 — the finding was resolvable but the
field has no live callers; the target may be dead code (follow up
with `/find-dormant`).

### Stage 2 — Profile the target (single scout)

**Pre:** `targets.json` exists. **Post:** `${REPORT_DIR}/profile.md`
exists.

Dispatch ONE scout (not fan-out) with `agents/enum-profiler.md`.
Substitute placeholders:

- `{{target_slug}}`, `{{model_class}}`, `{{field_name}}`,
  `{{field_file}}`, `{{field_symbol}}` — from `targets.json`
- `{{project_root}}` — `$(pwd)` absolute
- `{{targets_path}}` — absolute path to `${REPORT_DIR}/targets.json`
- `{{output_path}}` — absolute path to `${REPORT_DIR}/profile.md`
- `{{skill_root}}` — absolute path to
  `.claude/skills/extract-enum/`

Use `subagent_type=general-purpose`.

Tell the scout its output is judged only by the `profile.md` file it
writes at `{{output_path}}`: the file must follow the agent brief's
profile structure and use `knowledge/risk-context.md` for the risk
classification. A conversational summary does not satisfy Stage 2.

If the scout returns `profile_incomplete` or `targets_missing`, re-
dispatch once with a stricter "respond only with file-write
confirmation" nudge. If it fails twice, proceed with a partial
profile and flag the gap in the proposal.

### Stage 3 — Synthesize the proposal

**Pre:** profile exists. **Post:** `${REPORT_DIR}/proposal.md`
written.

Read `targets.json` + `profile.md`. Write `proposal.md` with this
structure:

```markdown
# Proposal — extract-enum: <Model>.<field>

## Target
`<field_file>::<Model>.<field>` — currently
`<CharField|TextField>(max_length=<N>, default=<default>)`.

## Distinct literals found (<N> sites)
<bullet list from targets.json.literals; include count per literal,
flag case-variants>

## Proposed enum
\`\`\`python
from django.db import models


class <Model>Status(models.TextChoices):
    PENDING = "pending", "Pending"
    IN_PROGRESS = "in_progress", "In progress"
    DONE = "done", "Done"
    FAILED = "failed", "Failed"
\`\`\`

## Field change
\`\`\`python
# before
<field> = models.CharField(max_length=<N>, default="<default>")
# after
<field> = models.CharField(
    max_length=<N>,
    default=<Model>Status.<DEFAULT_MEMBER>,
    choices=<Model>Status.choices,
)
\`\`\`

## Migration plan
1. **Schema migration** — add `choices` kwarg; `makemigrations`
   generates the AlterField operation.
2. **Data-migration check (pre-deploy)** — run
   `SELECT DISTINCT <field> FROM <table>` in production. If the set is
   NOT a subset of the enum values, the deploy will fail the
   `choices` validator. Reconcile with a one-off data-normalization
   migration first (see risks below).
3. **Caller migration** — update the <N> sites listed in the table
   below to use enum members.
4. **Lint enforcement** — re-run
   `scripts/lint/no_stringly_typed_status.py <field_file>
   <caller files>` — expect zero hits scoped to this field.

## Caller table
<table from profile.md: file | symbol | before | after>

## Data-migration risks
<bullet list — case-inconsistency, third-party bridges, tuple-choice
mismatches, read-only-never-written literals, etc.>

## Test matrix
Baseline (from `.claude/skills/_common/skill-conventions.md`):

\`\`\`bash
.venv/bin/python manage.py test \
  tests.test_site_capabilities tests.test_hydration_detector \
  --settings=app.settings_test_sqlite -v 2
\`\`\`

Plus subsystem-specific suites — grep `<Model>` in `tests/test_*`:

- `tests.test_<suite_a>` — covers the callers in <path>
- `tests.test_<suite_b>` — covers the callers in <path>

New characterization test (before migration): pin the current
behavior of every comparison path so the caller migration is proven
behavior-preserving.

Ruff baseline on the affected files:

\`\`\`bash
.venv/bin/ruff check <field_file> <caller files>
\`\`\`

## Stop condition
- Enum class added, field updated, `makemigrations` generates a
  clean migration.
- Every comparison site in the caller table uses an enum member.
- `scripts/lint/no_stringly_typed_status.py` reports zero hits on
  `<field>` in scope.
- Characterization tests (pre-migration behavior) pass unchanged.
- Baseline + subsystem-specific test matrix passes.

## Follow-on findings
<other stringly-typed fields surfaced during profiling; NOT part of
this proposal — each is a new `/extract-enum` invocation>

## Authorization
Human review required before execution. If approved, hand the
proposal to `/fix-workflow extract-enum:<target-slug>` (when that
variant ships) or to `/refactor-subsystem` for a multi-file change.
```

See `knowledge/risk-context.md` for project-specific gotchas the
proposal's risk section should cover (third-party bridges, Celery
resilience retries, legacy ExternalSource imports).

### Stage 4 — Effectiveness log

**Pre:** proposal written. **Post:** one line appended to
`reports/_meta/effectiveness.jsonl`.

```bash
LITERAL_COUNT=$(.venv/bin/python -c "import json,sys; print(len(json.load(open(sys.argv[1]))['literals']))" "${REPORT_DIR}/targets.json")
CASE_VARIANTS=$(.venv/bin/python -c "import json,sys; print(sum(1 for l in json.load(open(sys.argv[1]))['literals'] if l.get('case_variant_of')))" "${REPORT_DIR}/targets.json")
CONFIRMED=$(.venv/bin/python -c "import json,sys; print(len(json.load(open(sys.argv[1]))['comparison_sites']))" "${REPORT_DIR}/targets.json")
FIELD_SYMBOL=$(.venv/bin/python -c "import json,sys; print(json.load(open(sys.argv[1]))['field_symbol'])" "${REPORT_DIR}/targets.json")
FIELD_FILE=$(.venv/bin/python -c "import json,sys; print(json.load(open(sys.argv[1]))['field_file'])" "${REPORT_DIR}/targets.json")

.venv/bin/python scripts/log_effectiveness.py \
  --skill extract-enum \
  --scan-id "${TARGET_SLUG}" \
  --target "${FIELD_FILE}::${FIELD_SYMBOL}" \
  --findings-total "${LITERAL_COUNT}" \
  --buckets "{\"case_variants\": ${CASE_VARIANTS}, \"confirmed_sites\": ${CONFIRMED}}"
```

### Stage 5 — Summarize

Report to the user in ≤10 lines:

- Target (file + Model.field).
- Literal count + case-variant count.
- Caller count (by file, top 3).
- Risks flagged (one-line summary).
- Path to `${REPORT_DIR}/proposal.md`.
- Recommended next command:
  `/fix-workflow extract-enum:<target-slug>` (proposal-only today; hand
  the proposal to `/refactor-subsystem` for execution).

Do NOT start the execution step yourself. The proposal is the handoff
artifact.

## Replay / smoke

For a script-level replay, use a tiny project fixture with one
`models.Model` subclass carrying a `status = models.CharField(...)` and
one comparison or assignment site. Run `collect.py --target
<fixture-model>::status --project-root <fixture-root> --output
<tmp>/targets.json` and paste the stderr summary with literal,
case-variant, and caller counts. For Form A, a second replay may pass a
minimal `findings.json` containing a non-`extract_enum_candidate` bucket
and must show `collect.py` exits 2 before scanning.

## Non-goals

- Executing the refactor (that's `/fix-workflow` /
  `/refactor-subsystem`).
- Detecting new stringly-typed state (that's `/find-implicit-state`).
- Proposing a data-normalization migration for production rows —
  list the risk, don't write the migration. The migration is part
  of `/fix-workflow`'s job after human review of the risk.
- Opening more than one target per run. A second stringly-typed field
  surfaces as a follow-on finding; re-invoke the skill to handle it.
- Touching any file outside `reports/extract-enum/<target-slug>/`.

## When things go sideways

| Symptom | Action |
|---|---|
| Findings file missing (Form A) | Abort; tell user to run `/find-implicit-state` |
| Finding's `recommendation_hint` is `introduce_fk_candidate` | Abort; tell user to run `/introduce-fk` — this finding is tuple-identity, not stringly-state |
| `collect.py` returns 0 literals | Target has no callers — field may be dead code; suggest `/find-dormant` on the model file |
| `collect.py` errors `no Model subclass … declares … as CharField/TextField` — the `<file>::<field>` target is not a model field (it's a `@dataclass` attr, function return, module constant, or command-internal sentinel) | This skill's collector only walks model fields. The endpoint is a plain `str`-valued Enum (`enum.StrEnum` on 3.11+, or `class X(str, Enum)`), NOT TextChoices: define the enum next to the carrier, members `NAME = "value"`, swap each literal for `<Name>.<MEMBER>`, no migration. Do NOT `# noqa` a first-party sentinel (the noqa valve is for vendor-bridge literals only) |
| Model class ambiguous (multiple Models in file declare same field name) | Ask user for `--model-class <Name>` and retry Stage 1 |
| Scout says `targets_missing` | Re-dispatch once with stricter brief; if still missing, the `targets.json` is malformed — re-run Stage 1 |
| Case-variant explosion (>5 variants of same lower-cased form) | Flag in proposal risks; recommend a pre-migration data-normalization audit before human approval |
| Literal appears ONLY in webhook/bridge paths (ExternalSource, ScraperAPI, vendor APIs) | Mark as `third_party_bridge`; propose `# noqa: stringly-status: <reason>` for those comparison sites, NOT an enum member |
| Tuple-style `STATUS_CHOICES` already exists but lists different literals than scan found | Surface both sets in the proposal; flag the divergence as a migration risk |
