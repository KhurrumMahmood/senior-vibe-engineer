# Skill frontmatter — the agent decision contract

This file is the spec for skill `SKILL.md` frontmatter. It is the
authoritative source for what `scripts/skill_meta.py lint` enforces, and
what `/which-skill` reads to decide which skill matches a task.

The frontmatter is **not metadata for human discovery**. Skills are
primarily consumed by AI coding agents (Claude Code, Codex), and the
frontmatter is the contract those agents use to reason about *which*
tool fits a task and *what the tool is not for*. The negative space
(`not_for`, `escalate_to`) is what stops misapplication; it is not
optional.

## Existing fields (already in every skill)

| Field | Type | Purpose |
|---|---|---|
| `name` | string | Skill slug — must equal the directory name. |
| `description` | string | One paragraph, scout-readable. Surfaced in skill listings. |
| `argument-hint` | string | Inline syntax shown in `/help`. |
| `allowed-tools` | string (comma-list) | Tool names the skill needs. |
| `user-invocable` | bool | Whether the slash-command surface exposes it. |

## New fields — agent decision contract (PR1 onward)

Required on every NEW skill. Backfilled on existing 23 skills in PR2.

### `tier`

Which task-complexity tier this skill belongs to.

```
tier: feature
```

| Value | Meaning |
|---|---|
| `quick` | Skill targets trivial, bounded changes — almost no skill is `quick`-tier; the agent should usually just implement directly. Reserved. |
| `feature` | Cross-cutting feature, 1-3 day scope, touches one workflow. `/plan-feature` is the canonical example. |
| `system` | New subsystem or 2+ workflow feature. The granular planning chain (`/scope-feature` → `/impact-feature` → `/architecture-fit` → `/plan-spec`) lives here. |
| `new-project` | Greenfield scaffolding. `/init-project`. |
| `maintenance` | The cleanup/debug lanes — `/diagnose` plus the map/suspect/explain/refactor/guard loop (`/find-*`, `/map-*`, `/refactor-subsystem`, `/fix-workflow`, `/prevent-regression`, `/explain-code`). |
| `cross-cutting` | Used at any tier — `/decide`, `/which-skill`, `/teach-pattern`, `/triage-debt`, `/audit-decisions`. |

The tier is **not** a difficulty rating. It tells the agent which lane
of the workflow this skill belongs to.

### `job`

Which job this skill performs.

```
job: plan
```

| Value | Meaning |
|---|---|
| `plan` | Turns a goal into an executable spec (impact map + decision stubs + spec scaffold). |
| `map` | Produces a durable inventory doc. No refactor intent. |
| `suspect` | Surfaces candidates by smell. Read-only audit. |
| `explain` | Converts implicit contract into explicit proposal (no edits). |
| `refactor` | Executes an approved proposal end-to-end with tests + commits. |
| `guard` | Installs a diff-scoped lint rule + canonical-pattern entry. |
| `decide` | Authors / amends an ADR in the decision registry. |
| `triage` | Aggregates signals (effectiveness log + reports + drift) into a ranked queue. |
| `teach` | Produces an agent decision-walkthrough for a smell / pattern / decision. |
| `construct` | Supplies a canonical pattern at write time before drift exists. Constructive skills produce drafts, briefs, or implementation scaffolds that follow project doctrine from the start. |
| `diagnose` | Builds a feedback loop around a live symptom, identifies root cause, and proves the fix. |
| `meta` | Operates on the skill ecosystem itself (e.g. `/which-skill`). |

### `best_for`

Free-form prose. Two-to-four lines describing the **shape of task** the
skill matches. Concrete; written so an agent reading it alongside a task
description can match by string overlap and topic.

```yaml
best_for: |
  Cross-cutting feature, 1-3 day scope, touches one workflow.
  Needs impact assessment but not a new subsystem.
  Examples: per-site export-fingerprint TTL override; new
  field-extraction debug toggle on the Setup page.
```

### `not_for`

**The most important field.** Free-form prose listing tasks that look
like they could match but should *not* invoke this skill. Each item
should name the skill the agent should reach for instead.

```yaml
not_for: |
  Bug fixes (use /fix-workflow).
  New subsystems or 2+ workflow features (use /scope-feature).
  Trivial changes — one-line fix, rename, expose a field —
  implement directly; only run /decide if a real choice was made.
```

The `not_for` field is the single highest-leverage anti-misapplication
mechanism in the whole system. A skill with rich `not_for` text is
self-defending against the AI failure mode of "reach for the heaviest
machinery available." Skill authors must invest here.

### `escalate_to`

Names the skill the agent should switch to when the task overflows this
skill's scope. Free-form, but should reference an actual skill name.

```yaml
escalate_to: scope-feature when >1 subsystem touched
```

Optional. Omit for skills that have no natural escalation (e.g. `/decide`).

### `delegate_from`

Inverse of `escalate_to`. Names the skill that delegates *into* this
one as a sub-stage. Used by orchestrator skills that fan out to scouts
or chain to smaller skills.

```yaml
delegate_from: scope-feature for the impact-analysis sub-stage
```

Optional. Omit for skills that aren't called by other skills.

### `language` and `framework`

Portability seam. Declares the language / framework assumptions the
skill encodes. PR1 adds these on every new skill so PR3 can reorganize
the `_common/` directory into `_lib/{core,language,framework,repo}/`
without surprise.

```yaml
language: python
framework: django
```

Allowed values come from `capability-registry.yml`; validators must not
duplicate the list. `any` means that the procedure itself is portable. It does
not mean the skill scans or changes every language. Under the strict contract,
an `any` claim names and proves each `portable_subjects` entry.

Codex's native trigger mechanism uses `name` and `description`; the additional
fields are this multi-agent toolkit's routing, installation, and conformance
contract. Surface projections must preserve the trigger fields even when a
surface does not consume the additional metadata directly.

### Versioned capability contract

New portability claims opt into the strict schema. Legacy frontmatter remains
readable until the WP8 catalog migration, but it cannot be used as verified
support evidence.

```yaml
capability_contract: 1
layer: framework
binding: react
bindings: [javascript-typescript, react]
support: experimental
capabilities: [analysis.symbols, analysis.imports]
portable_subjects: [typescript]
capability_evidence:
  typescript:
    - kind: test
      path: tests/typescript-routing.py
      sha256: <64-lowercase-hex>
support_evidence:
  claim: {kind: skill, id: <skill-directory-name>}
  fixture:
    command: [<absolute-current-python>, tests/typescript-routing.py]
    cwd: .
    expected_stdout_sha256: <64-lowercase-hex>
  artifacts:
    - kind: test
      path: tests/typescript-routing.py
      sha256: <64-lowercase-hex>
  tools:
    - name: python-runtime
      command: [<absolute-current-python>, --version]
  platforms:
    - {system: Darwin, machine: arm64}
  evidence_hash: <canonical-envelope-sha256>
scans: [typescript]
```

- `layer`, `binding`, and optional `bindings` use registry identifiers.
- `capabilities` uses qualified `analysis.*`, `refactor.*`, or `guard.*`
  identifiers from the registry.
- `capability_evidence` maps each claimed subject or scan target to hashed,
  skill-relative file attestations and must include a test witness. Every
  declared capability test must be the single attested test directly executed
  by the fixture command, so multi-subject `any` and `scans:` coverage is
  actually executed. Use one attested integration-test wrapper when a suite has
  multiple underlying files. A scan also needs a registered adapter/native shim
  and a non-empty skill-local executable.
- `support_evidence` is evaluated mechanically: the validator checks artifact
  and envelope hashes, claim identity, command shape, registry-owned executable
  and tool-version policies, platform names, and scan support ceilings. The
  fixture command must execute an attested test artifact. Promotion reruns that
  test and the tool probes on the current platform; bare booleans, generic
  evidence, or support labels cannot promote a claim.
- Frameworks and tools are separate categories: React is a framework; Vite and
  Vitest are tools.

Keep the core `SKILL.md` concise. Put language/framework-specific idioms and
commands in one-level `bindings/<binding-id>.md` overlays so only the selected
variant is loaded. Do not copy the core procedure into a binding.

### `scout_model`

Optional. Hint to the orchestrator about the model class for parallel
scout fan-out work spawned by this skill.

```yaml
scout_model: cheap
```

| Value | Meaning |
|---|---|
| `cheap` | Scout work is read-and-classify against a known smell pattern. Safe on Haiku / Cerebras / GLM-class scouts; no cross-file synthesis required. |
| `careful` | Scout work needs Sonnet/Opus-class judgment — ambiguous inputs, cross-file reasoning, or judgment calls about whether a finding is real. Default. |

Default is `careful` — skills must opt into `cheap` explicitly. The
field is a *contract about scout fan-out only*, not the skill itself —
the orchestrator (Claude / Codex) reads it when spawning Agent
sub-tasks for parallel scouts and routes accordingly. Today routing is
manual (the SKILL.md prose names the model class); the field makes the
contract machine-readable so future orchestrators can route
automatically.

Skills that don't fan out to scouts should omit this field. Skills that
do fan out and stay on `careful` semantically declare "default
routing" — explicit is better than implicit.

## Optional task-packet fields (PR B-lite)

These eight fields are **optional** today. They give a skill enough
structure that an orchestrator (e.g. `/which-skill`) can return a
*task packet* — not just "use this skill" but "use this skill, on these
inputs, expecting these outputs, gated on this evidence."

The values are intentionally free-form right now. The linter only
enforces types (list / str / bool); the taxonomy of allowed values
will stabilize from real-world use before being locked into an enum.
This is the "no big-bang migration" principle — adopt on new skills,
backfill existing skills only when evidence supports it.

| Field | Type | Purpose |
|---|---|---|
| `lanes` | list[str] | Workflow lanes the skill belongs to. Examples: `[incident]`, `[system]`, `[maintenance, cross-cutting]`. |
| `stage` | str | Lifecycle stage. Suggested values: `discover` / `frame` / `execute` / `verify` / `learn`. |
| `entrypoint` | bool | True iff this skill is a lane-entry point. The orchestrator routes a fresh task to entrypoint skills first. |
| `consumes` | list[str] | Input evidence shapes. Examples: `[symptom, logs_or_report, repo_context]`. |
| `produces` | list[str] | Output evidence shapes. Examples: `[incident_report, regression_test, evidence_bundle]`. |
| `evidence_required` | list[str] | What the skill must produce before "done" can be claimed. Examples: `[reproduction_or_reason, root_cause, regression_test]`. PR D ships a soft gate (`scripts/evidence_gate.py`); PR G will turn it into a hard refusal. |
| `risk_triggers` | list[str] | Diff/context cues that escalate risk and should slow the skill down. Examples: `[production, customer, regression, outage]`. |
| `max_overhead` | str | One-line stopping rule when the skill is stuck. Example: `"Stop after 30 minutes without reproduction and write what is known."` |

Example — an incident-response skill might declare:

```yaml
lanes: [incident]
stage: execute
entrypoint: true
consumes: [symptom, logs_or_report, repo_context]
produces: [incident_report, regression_test, evidence_bundle]
evidence_required: [reproduction_or_reason, root_cause, regression_test]
risk_triggers: [production, customer, regression, outage]
max_overhead: "Stop after 30 minutes without reproduction and write what is known."
```

These fields are NOT gated on `tier:`. A legacy skill can adopt any
subset; the linter only complains about wrong types (e.g. `entrypoint: 1`
or `lanes: incident` instead of `lanes: [incident]`).

## Evidence gate (PR D)

Skills that declare `evidence_required` opt into a soft check that the
required evidence shapes were actually produced by a given scan. The
gate reads a per-scan `evidence.json` manifest and verifies that every
required token (a) appears in the manifest with a non-empty path and
(b) points at a file that exists on disk.

The manifest lives at `<scan-dir>/evidence.json`:

```json
{
  "skill": "incident-respond",
  "scan_id": "scan-20260501-120000",
  "produced_at": "2026-05-01T12:00:00Z",
  "evidence": {
    "reproduction_or_reason": "reproduction.md",
    "root_cause": "root-cause.md",
    "regression_test": "tests/incidents/test_incident_42.py"
  },
  "notes": ""
}
```

Paths are interpreted relative to the scan-dir unless absolute. Extra
keys are allowed and ignored — the gate only validates the
`evidence` map against the skill's `evidence_required` frontmatter.

Skill authors scaffold a stub manifest from their frontmatter:

```bash
python3 scripts/evidence_gate.py init \
  --skill incident-respond \
  --scan-dir reports/incident-respond/scan-20260501-120000
```

…and run the check before claiming "done":

```bash
python3 scripts/evidence_gate.py check \
  --skill incident-respond \
  --scan-dir reports/incident-respond/scan-20260501-120000
```

Exit 0 = pass (or skill has no `evidence_required`). Exit 1 = at least
one required token is missing or its declared file does not exist. Exit
2 = usage error (unknown skill, scan-dir absent, malformed manifest).

PR D is a soft gate — it never refuses to do other work and is not
wired into CI. PR F adds the CI hookup; PR G promotes failures to hard
refusals where appropriate.

## Full example — `/plan-feature`

```yaml
---
name: plan-feature
description: Feature-tier planning skill — produces an impact map and a
  proposed spec for a 1-3 day cross-cutting feature. Reads subsystem and
  workflow docs, fans out scout sub-agents per touched subsystem, drafts
  decision stubs for material forks, and scaffolds ai-docs/specs/<name>.md
  with status=proposed.
argument-hint: "<feature-name>"
allowed-tools: Bash, Read, Grep, Glob, Write, Edit, Agent
user-invocable: true

tier: feature
job: plan
best_for: |
  Cross-cutting feature, 1-3 day scope, touches one workflow.
  Needs impact assessment but not a new subsystem.
  Examples: per-site export-fingerprint TTL override; new
  field-extraction debug toggle on the Setup page.
not_for: |
  Bug fixes (use /fix-workflow).
  New subsystems or 2+ workflow features (use /scope-feature).
  Trivial changes — one-line fix, rename, expose a field —
  implement directly; only run /decide if a real choice was made.
escalate_to: scope-feature when >1 subsystem touched
delegate_from: scope-feature for the impact-analysis sub-stage

language: python
framework: django
---
```

## Linting

`scripts/skill_meta.py lint` validates:

1. Required existing fields present (`name`, `description`,
   `argument-hint`, `allowed-tools`, `user-invocable`).
2. **For skills declaring `tier`**: all new contract fields present
   (`tier`, `job`, `best_for`, `not_for`, `language`, `framework`),
   `tier` and `job` are from the allowed set, `best_for` and `not_for`
   are non-empty.
3. **For skills NOT declaring `tier`** (the existing 23 in PR1): only
   the existing-field check runs. PR2 will flip them to enforced.
4. **Optional task-packet fields** (any skill that declares them):
   types only — `lanes` / `consumes` / `produces` / `evidence_required` /
   `risk_triggers` must be lists of strings; `stage` and `max_overhead`
   must be non-empty strings; `entrypoint` must be a bool (rejects
   `entrypoint: 1`). Values are not yet enum-validated.
5. **Optional `scout_model`** (any skill that declares it): must be
   `cheap` or `careful`. Skills that don't fan out to scouts should
   omit the field.

Run:

```bash
.venv/bin/python scripts/skill_meta.py lint
```

Exit 0 = clean. Exit 1 = at least one diagnostic emitted to stdout.

## Why frontmatter, why not a separate index?

A separate index file (`.claude/docs/skill-index.json`) was considered
and rejected. The frontmatter lives next to the skill it describes; the
index would drift the moment a skill author forgets to update it. The
linter is the source of consistency, not a hand-edited index.

`/which-skill` reads frontmatter directly at runtime — there is no
build step. This keeps "skill author edits SKILL.md" as the only
authoring step, which is the friction-minimization criterion the whole
ecosystem is designed around.
