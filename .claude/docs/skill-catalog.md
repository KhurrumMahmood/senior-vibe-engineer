# Skill catalog — by job, not by verb

> **Plan, diagnose, map, suspect, explain, refactor, guard — plus
> construct, decide, and meta.**
>
> Optimal tooling for an AI-grown codebase continuously converts hidden
> structure into explicit structure, and one-off discoveries into
> repeatable guardrails. That mantra is the acceptance criterion for
> every skill in this catalog, and for any new one that joins it.

Skills are implementation — verbs like `/find-dormant` and
`/refactor-subsystem`. This doc organizes them by the **job** the human
or AI is trying to do, so "which skill should I reach for?" has a
one-step answer.

The maintenance loop:

```
  map ──► suspect ──► explain ──► refactor ──► guard ──┐
   ▲                                                   │
   └───────────────────────────────────────────────────┘
```

Plus a parallel **planning** entry point for new work, and **decide /
meta** skills that complement every tier:

```
  PLAN  (Quick / Feature / System / New-Project)
    │
    ▼
  DIAGNOSE  (concrete symptom -> feedback loop -> root cause)
    │
    ▼
  decide  (cross-cutting; at any tier when a real choice is made)
    │
    ▼
  which-shape  (meta; recommends the right operating loop)
    │
    ▼
  which-skill  (meta; recommends the right skill for an ambiguous task)
```

You don't have to enter at MAP every time, but every loop eventually
passes through GUARD — that's what keeps findings from recurring. New
work enters at PLAN; cleanup work enters at MAP or SUSPECT.

## How to pick a skill — decision walkthroughs

Most "which skill?" questions have an obvious answer if you name the
shape of the task. The walkthroughs below cover the common cases. When
the operating loop is unclear, run `/which-shape <situation>`. When the
loop is clear but the exact skill is not, run `/which-skill <task
description>`.

### One-line bug fix or trivial change

→ **Just fix it.** A typo in a comparison, a renamed field, a missing
log line — proceed directly to the edit. Run the targeted test for
the touched module.
→ Optional: `/decide` if the fix reveals a pattern issue (e.g. "we
keep typing `'in_porgress'` because there's no enum for this status").
→ NOT `/refactor-subsystem`, `/plan-feature`, `/fix-workflow`, or any
SUSPECT skill. Heavy machinery for a one-line change wastes context
and produces wrong-shape artifacts.

### Small feature: button, field exposure, simple endpoint

→ **Implement directly** with a test-first edit. Use the existing
service / view module that owns the surface.
→ Optional: `/decide` if a meaningful choice is being made (sync vs
async, FK vs enum).
→ NOT `/plan-feature` unless cross-cutting impact surfaces during the
edit (more than 2-3 files touched, or you find yourself re-deriving an
existing decision).

### Feature touching one workflow but multiple files

→ **`/plan-feature <name>`.** Reads subsystem docs, fans out scouts,
surfaces decision stubs, scaffolds a `proposed`-status spec.
→ Then `/refactor-subsystem` (if the feature involves restructuring)
or implement directly using the spec as the guide.
→ The spec is the handoff — implementation work resumes from
`ai-docs/specs/<feature-name>.md` without re-deriving impact.

### New subsystem or cross-subsystem feature (2+ workflows)

→ **The System-tier chain** when it ships in PR2: `/scope-feature` →
`/impact-feature` → `/architecture-fit` → `/plan-spec`.
→ NOT `/plan-feature` — the System tier exists specifically to keep
judgment pauses where scope can change shape.
→ Until PR2 ships, run `/plan-feature` and explicitly flag the cross-
subsystem nature in the spec's `## Architecture` section as a
follow-up for the System chain.

### Bug fix that touches multiple files

→ If the symptom is not reproduced or the root cause is unknown, start
with **`/diagnose <symptom>`**. The deliverable is a feedback loop,
root cause, verification, and prevention follow-up.
→ If a previous SUSPECT scan already identified the cluster or the fix
shape is known, use **`/fix-workflow`** with a natural-language
description or cluster ID.
→ NOT `/plan-feature` (planning is for net-new behavior, not bug fixes).

### Creating or revising a skill

→ **`/plan-skill <skill-idea>`** before writing the skill. It forces the
adversarial requirements pass: why not an existing skill, what false
trigger would hurt, what artifact proves completion, and what dogfood
case demonstrates the skill works.
→ Then implement the smallest useful skill, run `skill_meta.py lint`,
run matcher cases for positive/negative prompts, and dogfood once before
cataloging it.
→ Run **`/check-ecosystem-consistency`** before handoff for significant
skill changes. It snapshots the skill ecosystem, compares against the
last reviewed state, and flags follow-ups like stale counts, missing
catalog coverage, and possible `/which-shape` registry updates.
→ NOT direct skill authoring for broad or new workflow skills. Tiny
wording fixes to existing `SKILL.md` files can be edited directly.

### Inherited code you don't understand

→ **`/map-subsystem`** for a code-level inventory, OR
`/map-product-workflow` for a user-facing workflow surface.
→ Then `/explain-code` for behavioral annotations on the specific
file/symbol you need to trust.

### "Something feels wrong" — periodic audit

→ A SUSPECT skill matched to the suspicion:
- "Files keep growing" → `/find-omnibus`
- "We keep writing the same thing" → `/find-duplication` or
  `/find-semantic-duplication`
- "Status logic feels stringy" → `/find-implicit-state`
- "Read methods are surprising me" → `/find-query-mutation`
- "This path feels slow or branchy" → `/find-complexity-hotspots`
- "Views are too big" → `/find-layer-violation`
- "Workflow knowledge is everywhere" → `/find-workflow-duplication`,
  `/find-route-sprawl`, `/find-frontend-contract-drift`
- "The product surface feels brittle in cross-layer ways" →
  `/find-contract-drift`, `/find-async-lifecycle-drift`,
  `/find-dead-route-surface`, `/find-workflow-state-gaps`, or
  `/find-test-obligation-drift` depending on whether the concern is
  contracts, background lifecycle, reachability, UI states, or verification.
- "We have a shared UI primitive but every other page rolls its own" →
  `/find-frontend-duplication`
- "Comments feel stale, noisy, detached, or too thin to help" →
  `/find-comment-drift`
- "Old code might be dead" → `/find-dormant`
- "A baseline standard isn't applied everywhere it should be" →
  `/find-standard-gaps`

### Recording a real architectural choice

→ **`/decide <slug>`** to author a new ADR.
→ Threshold: the choice constrains future work, excludes an
alternative explicitly, or sets an expiration. Pure preferences do
NOT need an ADR.

### Genuinely uncertain — the operating loop is unclear

→ **`/which-shape <situation>`** — recommends the problem-solving loop
first: project intake, direct change, bug fix, feature shaping, legacy
stabilization, health audit, refactor execution, regression prevention,
or decision capture.
→ Use this when the user describes a messy situation and should not
need to understand the skill catalog.

### Tactically uncertain — multiple skills could apply

→ **`/which-skill <task description>`** — scores every skill's
metadata against the task; recommends the top match or "proceed
directly." Cheap to run; defends against agent misapplication.

### Anti-patterns: don't do this

| Wrong | Right |
|---|---|
| `/refactor-subsystem` for a typo | Just edit the file |
| `/plan-feature` for a 1-line endpoint addition | Implement directly |
| `/find-omnibus` for a 200-LOC view module | Use the lint, not the audit skill |
| `/decide` to record "I prefer 4-space indents" | That's a preference, not a decision |
| `/scope-feature` for a single-file change | Heavy chain for trivial work |
| Skip `/prevent-regression` after a cleanup | The same smell will land again |

## PLAN — design new work before touching code

**When to reach for a PLAN skill:** when adding new behavior, not
fixing existing behavior; when the change is large enough that grep
won't catch every call site; when a real choice is being made that
will outlive this PR.

| Skill | What it does | When |
|---|---|---|
| `/plan-feature` | Reads subsystem/workflow docs, canonical patterns, smells, decision registry; fans out scouts per touched subsystem (1-3); surfaces decision stubs for material forks; scaffolds a `proposed`-status spec at `ai-docs/specs/<feature-name>.md`. | Cross-cutting feature, 1-3 day scope, touches one workflow, needs impact assessment but not a new subsystem. |
| `/scope-feature` | Bounds-in / out + success criteria + non-goals for new subsystem or 2+ workflow work. | When `/plan-feature` would have to escalate. |
| `/impact-feature` | Full reachability + blast radius for System-tier work. | After `/scope-feature` confirms the bounds. |
| `/architecture-fit` | Check fit against decisions / patterns / smells; may emit decision proposals. | Before promoting a System-tier plan to spec. |
| `/plan-spec` | Promote `ai-docs/plans/<name>.md` → `ai-docs/specs/<name>.md` (status `planned`, `motivating_decision` linked). | Final step in the System-tier chain. |
| `/init-project` (PR3) | Greenfield scaffolding: conventions, lint/CI, initial decisions, baseline subsystem maps. | New project, not extending an existing one. |

PLAN skills produce the spec; they do NOT implement the feature.
Implementation is downstream — driven by the spec via
`/refactor-subsystem` or manual edits.

## DIAGNOSE — prove the bug before fixing it

**When to reach for a DIAGNOSE skill:** when there is a concrete
symptom but no trusted reproduction loop or root cause. Diagnosis is
not broad cleanup; it is the incident/debug lane that turns "broken"
into evidence.

| Skill | What it produces | When |
|---|---|---|
| `/diagnose` | `reports/diagnose/scan-<TS>/`: diagnosis index plus separate reproduction, root-cause, verification, cleanup-check files and evidence manifest. | Hard bugs, performance regressions, flakes, and reports where the tempting first fix would be guesswork. |

## CONSTRUCT — write with the pattern before drift exists

**When to reach for a CONSTRUCT skill:** when the correct project
pattern is already known and the agent is about to create a surface
that could drift if built from scratch. Constructive skills are the
write-time complement to SUSPECT scanners.

Initial constructive targets:

- **Agent brief authoring** — behavior-first handoffs with durable
  vocabulary, acceptance criteria, and scope boundaries.
- **Test-slice construction** — public-interface tests chosen before a
  feature or bug fix starts, with mocking only at real system edges.
- **UI/form construction** — shared UI primitives, controls, state, and
  responsive rules applied before template drift exists.
- **Skill construction** — `/plan-skill` now covers the requirements and
  validation gate; a future `/write-skill` can consume its brief.

## MAP — what's in this subsystem/workflow, and what owns what?

**When to reach for a MAP skill:** before editing an unfamiliar area;
when a code review asks "what's actually in this file?"; when a
subsystem's `docs/` page is stale or missing; when a user-visible
workflow spans routes, views, templates, JavaScript, and docs.

| Skill | What it does | When |
|---|---|---|
| `/map-subsystem` | Produces/refreshes `.claude/docs/subsystems/<name>.md` — file list, public surface, responsibility table, dependency graph, convention-compliance score. No refactor intent. | Before any edit to an unfamiliar subsystem; on demand to refresh a stale map. |
| `/map-product-workflow` | Produces/refreshes `.claude/docs/workflows/<name>.md` — workflow steps, routes, APIs, view/template ownership, JS boot globals, status providers, docs references, compatibility redirects. | At the start of a product area, when inheriting a large UI surface, or after major workflow work. |
| `/refactor-subsystem` (Phase 1 only) | Excavates the inventory as the first phase of a multi-file refactor. Has archaeology, chunking, SOLID audit. | When excavation and refactor are a single intent. For excavation alone, prefer `/map-subsystem`. |

## SUSPECT — where is this code doing something it shouldn't?

**When to reach for a SUSPECT skill:** periodic audits; after a major
feature land to sweep for bloat; when a review flags a hotspot and you
want systematic confirmation.

**Scan-scope contract:** every top-level `find-*` skill is accounted for in
`.claude/skills/_common/scan_scope_contracts.json`. The contract separates the
current executable modes from the target rollout modes and declares whether a
diff filters line findings, seeds a wider semantic analysis, or only triggers a
project audit. When adding or materially changing a SUSPECT producer, update its
row and run `.venv/bin/python scripts/check_scan_scope_contracts.py`; never add
`diff-lines` to a symbol, multi-site, or project finding just to make closeout
output smaller. Project/skill roots and ignores remain the file-universe layer;
the scope contract describes how an invocation uses that universe.

`which-cleanup/scripts/finding_envelope.py` is the shared adapter boundary. It
derives `line-filter`, `path-seed`, `project-trigger`, or `scope-neutral` from
the reviewed diff semantics, carries the originating scan request once at the
artifact level, and keeps producer-specific evidence/detail inside each
normalized finding. A new producer does not implement a second hunk parser or
silently clip wider findings; add its contract row and make the all-producer
conformance harness pass. Target modes are not routing claims until that
rollout's real-family and copied-library gates are recorded in the active plan;
the registry's `adapter_rollout` block then activates them without rewriting
the native entrypoint-mode history.

| Skill | What it detects | When |
|---|---|---|
| `/find-dormant` | Dead code, orphan endpoints, silently-broken handlers, orphan-entry-with-live-internals | After feature removals; after a prototype graduates into a real workflow; quarterly cleanup. |
| `/find-duplication` | Lexical (jscpd) + AST-shape clones | When edits feel repetitive; before `/refactor-subsystem`. |
| `/find-semantic-duplication` | Near-identical methods with divergent call paths; "shadow" helpers that look separate but do the same job | When `/find-duplication` is quiet but a workflow feels split. |
| `/find-omnibus` | Modules answering too many questions (SRP "and"-count > 2, high responsibility-cluster count × LOC) | When an edit requires understanding three separate domains from one file. |
| `/find-implicit-state` | Stringly-typed status fields, tuple-inferred identity (`where(status=X, created_at__gt=Y).first()`) | When a bug report mentions "jobs get stuck in state X" or "identity looks right but the wrong row came back." |
| `/find-query-mutation` | Methods named `get_*/fetch_*/load_*/list_*/find_*/check_*` that mutate | When a read looks cheap but isn't, or a caller is surprised by side effects. |
| `/find-complexity-hotspots` | Algorithmic / ORM / structural hot spots: nested loops, membership scans, sort-in-loop, QuerySet/manager calls inside loops, high-branch functions. Advisory report; findings need measurement or human review before optimization. | When a subsystem feels slow, a review flags a performance hotspot, or `/refactor-subsystem` needs a first-pass lead list. |
| `/find-layer-violation` | Views/tasks owning business logic (domain loops, LLM calls, multi-model transactions) | When view modules grow past a few hundred LOC or service extraction keeps getting deferred. |
| `/find-route-sprawl` | Product routes scattered through flat URL modules, missing include boundaries, duplicated alias surfaces | When a route file feels like a global junk drawer or a workflow prefix has no owner. |
| `/find-workflow-duplication` | Workflow authority repeated across layers: step labels, tab IDs, route literals, endpoint suffixes, boot payload keys, sidebar/dashboard knowledge | When sidebar, dashboard, templates, JS, and docs all seem to know the same workflow independently. |
| `/find-frontend-contract-drift` | Template-injected `window.*` globals, undeclared JS reads, repeated boot-global access | When frontend behavior depends on implicit globals from templates. |
| `/find-contract-drift` | Cross-layer product-surface contracts beyond boot globals: endpoint keys, DOM IDs, `data-*` selectors, template-called JS exports, and imported frontend-contract findings. | Before/after product-surface UI/API work where templates, static JS, and the workflow registry must agree. |
| `/find-async-lifecycle-drift` | Polling/job/export lifecycle hazards: unguarded polling, missing terminal handling, stale response risks, duplicate job dispatch, missing retry/cancel/resume controls. | Before/after work on background jobs, progress banners, downloads, exports, classification, or re-runs. |
| `/find-dead-route-surface` | Product-surface route/template/static reachability: prototype/dev routes, view references to missing templates, orphan templates, missing JS assets, unloaded JS. Reuses `/find-dormant` URL extraction for route inventory. | After prototype graduation, route moves, template splits, or periodic cleanup of a product surface. Use `/find-dormant` for whole-repo dead-code audits. |
| `/find-workflow-state-gaps` | Expected workflow states for tabs/panels: loading, empty, failed, retry/cancel/resume, disabled, mobile/responsive; includes workflow-duplication context. | Before shipping a new tab/panel or when a workflow works technically but feels incomplete under edge states. |
| `/find-test-obligation-drift` | Diff-to-verification advisory: backend changes without tests, UI/template/JS without UI-test coverage, skill changes without smoke tests, lint/tool changes without quality-tool tests. | Before final handoff on multi-file changes, especially AI-grown patches where verification scope can silently lag behind touched surfaces. |
| `/find-frontend-duplication` | Hand-rolled UI shells that bypass an existing UI primitive (Cotton component, React component, partial); JS helper forks (same name, drifted bodies); CSRF wrapper gaps | When templates and static JS look like every page rebuilt the same shells from scratch; before extracting a new primitive. |
| `/find-doc-route-drift` | Documented route strings and redirect claims that disagree with URL/view reality | When docs mention workflow routes or a review spots route drift. |
| `/find-comment-drift` | Comments/docstrings/JSDoc that no longer carry senior-engineer signal across Python, JavaScript/JSX, TypeScript/TSX, and HTML/templates: detached banners, narration comments, missing/thin public class docstrings, stale terminology, JS/TS functions needing JSDoc, thin ceremonial JSDoc, noisy section comments, and malformed doc references. Advisory report; its bad-comment subset is mirrored by the diff-scoped `comment-drift` lint. | When an AI-grown surface feels sour to read, after a route/UI cleanup, or before doing a focused explanatory-code pass. |
| `/find-folder-topology-drift` | Bidirectional ADR 0006 audit — flat folders with N≥3 same-prefix sibling files (promote), `tests_*.py` populations missing a `tests/` subfolder, AND folder packages whose source-module count fell below ≥3 (demote). Folders earn packaging at threshold and lose it below threshold. | When a `views/`, `tasks/`, or `services/` directory feels like a junk drawer of `<prefix>_*.py` siblings; or when a previous decomposition's folder has shrunk back to 1-2 source modules. |
| `/find-stale-artifacts` | Working-artifact hygiene for non-code surfaces — abandoned plans, in-flight plans past a soft staleness budget, aged `reports/<skill>/scan-<TS>/` directories not pointed at by `latest`, and orphan top-level `reports/*.md` files. Sibling to `/find-dormant` for code. | Periodic (monthly / quarterly) sweep of `ai-docs/plans/` and `reports/` to keep working-artifact directories from accumulating cruft as side effects of active work. |
| `/find-standard-gaps` | Sites where a declared baseline standard should apply but doesn't — each standard is an idea with an executable `ast` detector (`call_matches` + `enclosed_by`/`requires_kwarg`). Generalizes hand-written AST lints: declare a standard once instead of authoring a bespoke lint. Detection-only. | Periodic security/resilience sweep; when a guard class ("X must be inside a `try`", "Y must pass a timeout") should hold project-wide; after adding a standard to the standards file. |

### Product-Health Pilot Workflow

The five product-health SUSPECT skills are sensors first and guardrails
second. In the pilot, run them advisory-only:

- For new product-surface work, run the relevant scanner before implementation
  for a baseline, run it again after, then fix high-confidence *new*
  findings.
- Run one scanner when the concern is clear. Run all five only for broad
  health sweeps, cleanup passes, or handoffs where the product surface is
  unfamiliar.
- For cleanup, run all five, feed the reports into `/triage-debt`, fix the
  top clusters with `/fix-workflow` or manual edits, then use
  `/prevent-regression` only after the pattern repeats cleanly.
- Promote a band to diff-scoped lint only after fixture coverage, at least
  one real fix, explicit false-positive handling, and low noise on the
  product surface.
- Record false positives in fixtures or skill knowledge, not memory.

## EXPLAIN — what contract does this code actually enforce?

**When to reach for an EXPLAIN skill:** when a SUSPECT scan flags
something and the fix isn't obvious until the hidden contract is
written down; when legacy code needs to be trusted before it can be
changed.

| Skill | What it produces | When |
|---|---|---|
| `/explain-code` | `reports/explanations/<target>.md` — annotated behavior, extracted invariants, unexplained regions flagged. No code edits. | When a file needs to be *understood* before it can be changed, and the understanding should outlive the conversation. |
| `/unify-shadows` (proposal mode) | Typed-strategy-interface proposal for N shadows flagged by `/find-semantic-duplication` | When `/find-semantic-duplication` returns a `keep_separate` shape but the divergent contracts are actually a missing interface. |
| `/extract-state-type` | `@dataclass` / `TypedDict` proposal + migration plan for a mutable-dict state | When a function operates on a dict whose shape is implicit. |
| `/extract-enum` | Typed-enum proposal (e.g. `TextChoices`, `StrEnum`) + call-site migration | When `/find-implicit-state` finds stringly-typed status at N≥3 sites; when new feature work would otherwise add callers around a legacy tuple-choice state field. |
| `/introduce-fk` | FK + data migration (backfill + set-NOT-NULL two-step) | When `/find-implicit-state` finds tuple-inferred identity. |
| `/extract-workflow-registry` | Canonical workflow-registry proposal — step id, label, route, visibility, status provider, active tab, template owner, frontend boot keys, endpoint payloads | When product workflow knowledge is duplicated but the fix needs an explicit owner before code moves; when a new workflow feature is about to add pages, boot keys, or scoped endpoints. |
| `/extract-cotton-primitive` | UI-primitive proposal at `reports/extract-cotton-primitive/<slug>/proposal.md` — component shape, variable declarations, JS partner, before/after migration table for every profiled callsite, doctrine compliance check, lint name. | When `/find-frontend-duplication` flags a hand-rolled-shell cluster that crosses the three-callsites/two-templates threshold; or when you already know a primitive is missing and want the proposal directly via `/extract-cotton-primitive <category>`. |
| `/organize-project-structure` | Repo-wide folder-structure design around recursive folder summaries, boundary discovery, ideal-vs-constrained topology, source-material preservation, folder-worth judgment, and implementation options. May produce a `/move-path` dry-run plan, but applying it is a separate decision. | When historical top-level folders such as inputs/outputs/archive dumps make a repo hard to skim, or when a proposed project tree needs review under framework/tool/human constraints. Use `/move-path` directly for a known single move. |
| `/propose-folder-reorganization` | Per-cluster proposal at `reports/propose-folder-reorganization/<slug>/proposal.md` — current → proposed tree, file-move table, import-impact summary, characterization-test matrix, migration sequencing, stop condition. Promote mode (flat → folder) and demote mode (folder → flat) per ADR 0006 Rule 5. | When `/find-folder-topology-drift` flags a `flat_prefix_cluster`, `tests_by_prefix`, or `sparse_folder_package` and you want the migration plan before `/refactor-subsystem` executes it. |
| `/propose-boundary` | Boundary-extraction proposal at `reports/propose-boundary/<slug>/proposal.md` — candidate seams (cluster contents, proposed public API, backward-compat shim shape, reach-into-private caller list, characterization-test matrix). Read-only; pairs with smell 9 (missing-boundary) in `architectural-smells.md`. Works on file, directory, or skill-directory targets (skill targets parse `## Phase N` headings as virtual symbols). Decided in: host project's ADR on staged boundary rearchitecting. | When sibling modules reach into each other's private helpers, change-amplification touches the same N files for every feature, or a large composite skill is itself a candidate for splitting into specialized sub-skills. |

Contract-makers (`/extract-state-type`, `/extract-enum`, `/introduce-fk`)
each pair with a SUSPECT detector. The SUSPECT finds the smell; the
EXPLAIN skill proposes the explicit form. REFACTOR skills execute it.

## REFACTOR — how do I change shape without changing behavior?

**When to reach for a REFACTOR skill:** when the proposal from EXPLAIN
is approved; when a SUSPECT cluster has a known fix shape.

| Skill | What it does | When |
|---|---|---|
| `/fix-workflow` | Executes one cluster (duplication, dormant, shadow, etc.) end-to-end — reads target, picks a fix-shape playbook, edits, tests, commits | After any `/find-*` audit; for targeted cleanups. |
| `/move-path` | Deterministic batched file/directory moves with virtual after-tree reference rewriting, dry-run/apply/check modes, Git-aware moves, Markdown/backtick/path reference updates, and blocked/suggested uncertainty buckets. | When many files or folders need to be renamed or moved and repo references should update in one batch. Especially useful for Markdown-heavy docs/KBS, repo-layout reshapes, and safe path moves before committing. Not for glossary-level concept renames or behavior-changing subsystem splits. |
| `/rename-concept` | Read-only assessment of a glossary-worthy domain-concept rename: scope gate, lifecycle table, and two-band completeness gate for identifier/prose drift. Escalates to `/move-path` only when the concept rename also requires filesystem path moves. | When a domain term is being superseded across glossary, code identifiers, prose, and cross-tool mirrors. Not for local file moves or narrow symbol renames. |
| `/refactor-subsystem` | Multi-file, spec-driven, scout-fanned structural refactor with two-commit discipline and characterization tests | For splits (omnibus → package), migrations (N shadows → typed interface), and decompositions (god-class → directory package). |
| `/unify-shadows` (execute mode) | Hands a finished proposal to `/fix-workflow semantic:<id>` | Pairs with the proposal-mode invocation. |

## GUARD — how do I stop this from recurring?

**When to reach for a GUARD skill:** after every successful
refactor — the finding that justified the refactor is evidence the same
shape can land again.

| Skill | What it produces | When |
|---|---|---|
| `/prevent-regression` | Diff-scoped lint rule (ruff, custom AST, or narrow lexical guard) + bad/good fixtures + pre-commit wiring + CLAUDE.md Canonical Pattern entry | After `/fix-workflow` closes a cluster whose shape is detectable with a path-scoped rule; after a new feature establishes a convention likely to regress. |

GUARD is not a one-shot install — it's the **every-cleanup tail**.
A fix without a GUARD is an open door for the same bug to walk back in.

## PROJECT ADAPTATION — how does this portable kernel become local?

**When to reach for a PROJECT ADAPTATION skill:** when installing or
dogfooding engineering-skills in a host repo; when the adapter facts
are stale; or when a project needs its human intent, risk posture, and
"do not standardize this mess" guidance captured before agents start
canonizing local patterns.

| Skill | What it does | When |
|---|---|---|
| `/adapt-project` | Discovers objective host-project facts — stack, commands, tests, CI, docs, source roots, domain terms, sensitive surfaces, existing guardrails, and skill overlays. Writes `adapter.yml` and a human report; host writes require `--apply`; `--no-host-write` supports dogfood against reference repos with an external artifact root. | First pass on a new host repo; after stack/test/CI changes; before generating project-specific skill overlays. |
| `/project-interview` | Drafts the human-approved project profile — purpose, maturity, critical workflows, risk posture, desired direction, intentional tradeoffs, known-bad legacy patterns, and open questions. | After `/adapt-project` discovery, or whenever a repo's direction has changed enough that agents need new priors. |

The split is deliberate: `/adapt-project` can discover what exists, but
only `/project-interview` can capture what the project is trying to be.
Common patterns in a vibe-coded or inherited repo are observations, not
canonical patterns, until the profile says they are healthy.

## DECIDE & META — cross-cutting at every tier

These skills don't fit one job in the loop. They complement every
other skill — at any tier, at any stage.

| Skill | What it does | When |
|---|---|---|
| `/decide` | Authors or amends an ADR under `ai-docs/decisions/<NNNN>-<slug>.md`. Reads canonical-patterns.md and architectural-smells.md to suggest related-pattern / related-smell backrefs. Smallest first-class artifact in the senior-engineer ecosystem. | When a real choice is being made that constrains future work, excludes an alternative, or sets an expiration. Threshold: 2-5 ADRs/quarter. |
| `/which-shape` | Strategic router. Reads `which-shape/shapes.yml` plus `.engineering/project/` adapter/profile state and recommends an advisory operating loop with first next step, sequence, and stop/reassess condition. | When the situation is ambiguous at the loop level: unknown project, messy legacy code, broad health question, recurring failure, or unclear feature/refactor/decision shape. |
| `/which-cleanup` | Diff-driven, scope-tiered closeout router (ADR 0023). Resolves what changed (files / `--staged` / `--changed-from` / `--commit` / `--range` / `--area` / `--since`), sizes a scope band, and recommends cleanup skills bucketed pre-baseline / post-sweep / guard-tail from `subsystems.yaml` adjacency + each skill's `job:`. Registry-optional: with none, degrades to universal floor + band. Escalates checklist → scoped scout fan-out → plan + spec stub. Also a backward `coverage.py audit`. Advisory; read-only. | At task/commit closeout: "I changed these files — what cleanup do I owe, scaled to how big the change is?" The diff-scoped counterpart to periodic `/triage-debt`; the `task-closeout` shape in `/which-shape` points here. |
| `/converge` | After-phase convergence gate (ADR 0031). Models the work-in-progress as a small value graph ("done" = every dimension holds at once), assesses each node on cited evidence, and emits a fixed verdict: phase_status (advance / repair / branch / park / discard), weakest nodes, the single next necessary step, the success gate, the stop condition, and a do-not-do-next refusal list. Advisory; emits the verdict and stops. | After a meaningful phase — refactor executed, sweep finished, design pass produced — when the next move is about to be chosen by momentum. Answers "is this thread done, what's the one necessary next step, when do we stop?" Complementary to `/which-cleanup` (which picks cleanup skills from the diff). |
| `/check-ecosystem-consistency` | Diff-aware ecosystem audit. Snapshots skills, `/which-shape` references, public count claims, and catalog coverage; compares against `.claude/ecosystem/last-state.json`; writes `reports/check-ecosystem-consistency/scan-<TS>/`. | After adding/removing/materially changing skills or editing the shape registry/catalog. Use `--update-state` only after the findings are reviewed. |
| `/which-skill` | Recommender. Reads every SKILL.md frontmatter (tier, job, best_for, not_for) and ranks against a free-text task description. Returns top match or "proceed directly". | When the right skill isn't obvious, especially at the start of a non-trivial task. Defends against funneling a 1-line fix into heavy planning machinery. |
| `/plan-skill` | New-skill intake and hardening gate. Produces a skill brief, adversarial requirements review, validation plan, and evidence manifest before implementation. | Before creating a new skill or materially revising an existing one. Forces the "why not an existing skill?" and "how will we dogfood this?" questions up front. |
| `/engineer-init` | Bootstraps the ecosystem runtime — checks Python >= 3.11, creates `.venv`, installs `requirements.txt`, wires pre-commit hooks when the repo is git-tracked, and verifies a script-backed skill runs to exit 0. Idempotent; `--check` reports status without installing. Prompt-only, no helper script. | Once per clone before invoking any script-backed skill; or when a skill errors out with a missing-module / dependency failure. |
| `/triage-debt` | Pure aggregator. Scores accumulated debt across `reports/_meta/effectiveness.jsonl`, every `reports/<find-*>/latest/`, `scripts/specs.py audit`, and `scripts/decisions.py audit`. Produces a ranked queue at `reports/triage-debt/scan-<TS>/queue.md`; each entry recommends the next skill to invoke. | Periodic (weekly / pre-release) "what's accumulating" sweep. After a busy refactor batch, before planning a new feature. |
| `/teach-pattern` | Layered briefing on one rule, smell, ADR, or canonical-pattern anchor — rule, why, exemplar, counter-example, enforcement. The `--for-agent <context>` flag re-frames the briefing as "given THIS PR context, here's why X is right and Y is wrong." | Onboarding (human or new agent) to a project convention; mid-PR agent reasoning ("why does the lint say X?"); converting a one-line rule into the full backstory. |
| `/gut-check` | Instinctive "does this look dumb?" reaction pass over a plan markdown, a commit diff, or a free-form architecture summary. Emits 3-5 cited smell reactions split into `un-decided` (raw signal — no precedent/ADR covers them) and `decided-but-still-smell` (an ADR or precedent contradicts the smell — surface both halves so the human can decide whether to re-litigate). Confidence-banded (`strong-smell` / `weak-smell` / `style-preference`; the last is hidden unless `--include-style`). Prompt-only, no helper script. | Right before a plan goes from "designed" to "built"; right after a diff lands locally and before pushing; when an architecture description feels off but you can't articulate why. Signal, not verdict — the highest-leverage output is decision-conflict flagging. |
| `/audit-decisions` | Cross-cutting drift scanner for the decision registry. Wraps `decisions.py audit/link-check` plus four extra checks (code-ref orphans, broken supersession back-references, stalled `proposed > 30d`, missing `applies_to:` paths). Output: `reports/audit-decisions/scan-<TS>/drift.md` with one resolution command per row. | Periodic (monthly / pre-release) hygiene of the decision registry. After a batch of refactors that shuffled `applies_to:` paths. |

`/decide` should be invoked WITHIN other skills' flows when a fork
needs an ADR (e.g., `/plan-feature` Stage 3 may invoke `/decide` for
each material fork). `/which-shape` chooses the operating loop when the
situation is broad or unclear; `/which-skill` chooses the tactical skill
inside a known loop. `/triage-debt`, `/teach-pattern`, and `/audit-decisions` are the
**senior-engineer surface** — they make accumulation visible, turn
rules into briefings agents can reason about mid-PR, and prevent the
decision registry from rotting. All three are read-only — the user
picks the recommended next command.

## IDEAS — capture, mature, and promote development ideas

**When to reach for an IDEAS skill:** when an idea worth remembering
surfaces (feature, refactor, prompt shape, harness pattern, research
probe); when a planning flow needs prior-art lookup; when stalled work
needs surfacing; or when bootstrapping an existing project that has
working backlog / lessons but no ledger.

Two-tier architecture (see ADR 0013):

- **Tier 1 — Idea ledger** (`.claude/ideas/log.jsonl`): append-only
  JSONL. One intake per idea; events for transitions, markers, edges,
  adoption notes. Bar for entry: *"would future-me want this back?"*
- **Tier 2 — Pattern library** (`.claude/patterns/<slug>.md`): one
  Markdown file per pattern, promoted at `adoption_count >= 1`. The
  `generalizability` qualifier (`single-constraint-set` →
  `validated-across-N` → `broadly-applicable`) graduates as adoptions
  accumulate. ≥1-adoption gate is deliberately lower than the
  ≥3-siblings rule for folder packaging (ADR 0006); documentary
  promotion costs one Markdown file, not navigation friction.

| Skill | What it does | When |
|---|---|---|
| `/track-idea` | Canonical write surface for Tier 1. Creates an intake; appends event records (transition / marker / edge / adoption / dev-note / note). Validates against the schema. | Whenever a new idea worth remembering surfaces; whenever an existing idea changes state, gains a marker, accumulates an edge, or earns an adoption. |
| `/find-orphaned-ideas` | Multi-mode detector — `file-orphan` (intake without recent events), `stall` (in-flight past budget), `plan-dropout` (intake referenced by a plan that shipped without it), `harvest-opportunity` (lesson with `has-more-potential`), `dormant-with-potential`. `--harvest` surfaces lesson-derived candidates the ledger hasn't promoted yet. | Periodic sweep (weekly / pre-release) for ideas that slipped without being closed; pre-planning surfacing of dropped or unfinished ideas. |
| `/query-patterns` | Tier 2 lookup. Filters by problem class, generalizability, status; ranks by adoption evidence and constraint match. | At the start of `/plan-feature`, `/scope-feature`, `/architecture-fit`, or any planning surface that should consider prior art first. Inline-template sibling at `.claude/docs/query-patterns-inline.md` for ad-hoc lookups. |
| `/brainstorm-ideas` | Exploration / bulk capture: web research + AI ideation emit `proposed` intakes. The **single writer for all bulk ledger writes** — `/extract-existing-ideas` hands surviving candidates off here so dedup and validation stay centralized. | When opening a new problem space and wanting a survey of approaches captured to the ledger. |
| `/mature-existing-ideas` | Periodic research pass against best practices, failure modes, alternatives. Appends a `research:` note as a marker event; can clear `needs-research` / `underdeveloped` markers when satisfied. Three forms: A (specific slug), B (`--all-needs-research`), C (`--topic <term>`). | When an entry carries `needs-research`; when a planned feature will rely on a `proposed` idea that hasn't been validated against external practice. |
| `/extract-existing-ideas` | Bootstrap / catch-up reader. Walks `BACKLOG.md` and `lessons.md`, classifies candidates NEW vs WOULD-COLLIDE against the live ledger, presents for review, hands survivors to `brainstorm.py` for the actual write. Read-only by default. | Once per project, to bring existing backlog + lessons into the ledger without retyping. Also catches items added to backlog but never tracked through `/track-idea`. |

Deferred (open gaps, not yet shipped):

- `/promote-idea-to-pattern` — explicit Tier 1 → Tier 2 promotion with
  adoption-evidence capture. Currently handled inline in `/track-idea`
  + manual `.claude/patterns/<slug>.md` authoring.
- `/audit-ideas` — lineage back-pointers, supersession resolution,
  stale-flag transitions. Currently handled by manual harness runs.
- `/skill-spec-conformance-validation` — checks that a skill's
  emissions match its declared frontmatter contract. Manual surrogate
  via `/mature-existing-ideas` against the skill's own ledger entry
  until the dedicated skill ships.

Validation harness: `.venv/bin/python .claude/tests/ideas/run_harness.py`
covers seven fixture scenarios (stalled-spike, plan-dropout,
harvest-opportunity, ≥1 promotion eligibility, supersession-chain
integrity, resurrection of `done outcome=rejected` ideas,
extraction-truth-set). Run before changes to `_common/ideas_lib.py` or
any IDEAS skill.

Cross-references:

- `ai-docs/decisions/0013-idea-tracking-system.md` — system rationale,
  alternatives considered, consequences
- `.claude/docs/idea-ledger.md` — Tier 1 schema, state machine,
  projection rules
- `.claude/docs/pattern-library.md` — Tier 2 schema, promotion gate,
  qualifier graduation
- `.claude/docs/query-patterns-inline.md` — inline prompt template
  sibling to `/query-patterns`
- `.claude/ideas/README.md` + `.claude/patterns/README.md` — direct-
  reader summaries for the on-disk surfaces

## Cross-reference: canonical flow

The common path through the loop, in order:

1. `/which-skill <task>` (optional, when uncertain) — picks the
   right entry point.
2. **For new work:** `/plan-feature <name>` → spec → `/refactor-
   subsystem` or implement.
3. **For concrete bugs:** `/diagnose <symptom>` → root cause +
   verification → fix directly or hand off to `/fix-workflow` →
   `/prevent-regression` if the prevention shape is repeatable.
4. **For cleanup work:** `/map-subsystem` or `/map-product-workflow`
   → `/find-<smell>` → `/explain-code` or contract-maker →
   `/fix-workflow` or `/refactor-subsystem` → `/prevent-regression`.
5. **For new skills:** `/plan-skill <idea>` → implement the smallest
   skill → dogfood + matcher/lint/evidence checks → catalog it.
6. **At any step:** `/decide` when a real choice is made.

Skipping steps is fine when the target is already well-understood.
Skipping GUARD is a mistake — it turns every cleanup into a recurring
tax. Skipping `/decide` when a choice is real means the next agent
will re-litigate it.

## Workflow recipes

**Start of a new product area.** Run `/map-product-workflow` if there is
a user-visible workflow, then `/extract-workflow-registry` before step
knowledge spreads across routes, templates, and JS. For the first
material feature, `/plan-feature` produces the spec; subsequent
features can extend the spec rather than re-mapping.

**Greenfield project.** PR3's `/init-project` will scaffold conventions
+ initial decisions + baseline subsystem maps. Until then, manually
seed `.claude/docs/subsystems/`, `ai-docs/decisions/0001-*.md`, and the
canonical-patterns / architectural-smells docs.

**Inheriting a large project.** Run `/map-product-workflow` for the main
surface, `/map-subsystem` on the largest owners, then
`/find-route-sprawl`, `/find-workflow-duplication`,
`/find-frontend-contract-drift`, `/find-omnibus`, and
`/find-layer-violation`. Triage user-visible instability before broad
SOLID cleanup. Record any non-obvious choices via `/decide`.

**Adding a 1-3 day feature to an existing workflow.**
1. `/which-skill <feature description>` — confirms feature-tier fit.
2. `/plan-feature <feature-name>` — produces spec at
   `ai-docs/specs/<feature-name>.md`.
3. Implement (manual edits or `/refactor-subsystem` if structural).
4. `/decide` if any material fork was made along the way.
5. If the fix shape is recurring, `/prevent-regression` for the lint
   that catches it next time.

**Regular maintenance.** Per change, run diff-scoped lints and only the
relevant skill checks. Monthly, run route/workflow/frontend drift scans
on major product workflows. Quarterly, refresh workflow and subsystem
maps and review `reports/_meta/effectiveness.jsonl`.

**After major feature/refactor work.** Refresh affected maps, run
targeted SUSPECT skills, and promote only repeatable/lintable smells to
`/prevent-regression`. If a real architectural choice was made, run
`/decide` to capture it before context evaporates.

**Before a large architecture refactor.** Map first, suspect second,
explain the hidden contract, add characterization tests, refactor, then
guard the shapes that can recur. Use `/decide` for each fork in the
refactor design.

## Accepting new skills

Run `/plan-skill <idea>` before adding anything broad or new to this
catalog. Tiny wording fixes can skip it. The standing rules:

1. **It must fit exactly one job.** Skills that blur MAP + REFACTOR
   (like today's `/refactor-subsystem`) tend to produce reactive maps
   that only exist when you're about to edit. New skills should pick
   one lane.
2. **It must leave an audit trail.** All `find-*` and `refactor-*`
   skills append to `reports/_meta/effectiveness.jsonl`. New skills
   follow the same pattern.
3. **It must produce an artifact a human can read without the skill
   loaded.** Reports, proposals, explanations — each stands on its
   own. Don't rely on skill-internal context.
4. **It must be dogfooded once before cataloging.** The dogfood case
   can be a real host-project task or a small fixture, but it must
   exercise the trigger path and the output artifact. Add a negative
   prompt when false invocation is a realistic risk.

New skills also declare the agent decision contract in frontmatter
(`tier`, `job`, `best_for`, `not_for`, `language`, `framework`) per
`.claude/skills/_common/skill-frontmatter.md`. The contract is what
makes `/which-skill` work.

## Related docs

- `.claude/skills/_common/skill-frontmatter.md` — the agent decision
  contract every new skill declares.
- `.claude/skills/_common/portability-roadmap.md` — the future
  `_lib/{core,language,framework,repo}/` reorg.
- `.claude/docs/language-support-development.md` — the current contributor
  contract for native-tool selection, provider tiers, conformance, batching,
  and promotion of shared language infrastructure.
- `.claude/docs/architectural-smells.md` — catalog of the eight
  architectural smells the SUSPECT skills target.
- `.claude/docs/canonical-patterns.md` — the law every PLAN /
  REFACTOR / GUARD skill respects.
- `ai-docs/decisions/README.md` — ADR registry conventions.
- `reports/_meta/README.md` — the cross-time effectiveness log that
  every skill appends to.
- `.claude/skills/_common/skill-conventions.md` — project-agnostic
  skill mechanics (report layout, scout outputs, hygiene).
- `.claude/skills/_common/interface-depth.md` — shared deletion-test,
  test-surface, and adapter-reality rubric for extraction/refactor
  decisions.
