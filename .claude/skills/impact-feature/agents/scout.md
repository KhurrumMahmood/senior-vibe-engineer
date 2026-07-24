# Scout brief — impact map for one subsystem (System tier)

This file is a **prompt template** the orchestrator expands and sends
to a sub-agent. Placeholders are double-brace `{{name}}`. The
orchestrator either calls `dispatch_scout.sh` (subprocess fan-out,
nesting-safe) or the `Agent` tool with
`subagent_type=general-purpose` — both expand the same template.

Fresh sub-agent, no prior context. Read the plan and the subsystem
doc; everything else lives inline below.

---

## Prompt template (starts below the `---`)

You are mapping the impact of a System-tier plan on **one** subsystem
of this codebase. The plan is at `{{plan_path}}` and already has §1
(Scope & Bounds) and §2 (Success Criteria) filled — read them; do not
second-guess scope. Your job is to answer two questions for THIS
subsystem and write a single markdown report:

1. **Where would this work land in this subsystem?** (call sites,
   model touchpoints, route boundaries, test surfaces)
2. **What invariants must the work preserve?** (load-bearing
   side-effects, queue pinning, mixin requirements, signal handlers,
   ordering constraints)

You are **not** doing architecture-fit analysis (that's
`/architecture-fit`). You are **not** picking between alternatives.
You are **not** scaffolding a spec. You produce ONE markdown file at
`{{output_path}}` and nothing else.

### How your output is judged

- The file at `{{output_path}}` exists and contains the required
  sections under "Output contract" below.
- Findings cite the concrete artifacts you read: file paths, symbols,
  tests, routes, workflows, and the behaviors-to-preserve they imply.
- Any out-of-scope impact is isolated under that heading instead of
  silently expanding the plan scope.
- Chat-only summaries do not count. Write the file, then reply with a
  short confirmation.

### Inputs

- Plan name: `{{plan_name}}` (kebab-case slug, also the plan's
  `name:` frontmatter)
- Plan path: `{{plan_path}}` — read §1-2 to understand scope; do NOT
  expand scope beyond what's in §1.
- Subsystem: `{{subsystem}}` (matches a file under
  `.engineering/docs/subsystems/<subsystem>.md` if present)
- Project root (absolute): `{{project_root}}`
- Skill root: `{{skill_root}}`
- Write your output here: `{{output_path}}`

### Knowledge you MUST consult

Read in this order, skipping any that don't exist:

1. `{{plan_path}}` — plan §1-2. The "in scope" list bounds your
   investigation. If you find impact OUTSIDE that scope, note it but
   do not expand the scout's scope to match.
2. `{{project_root}}/.engineering/docs/subsystems/{{subsystem}}.md` — the
   inventory + responsibility table. Treat as ground truth for what
   the subsystem currently does. If missing, scan the relevant code
   directory yourself and form your own one-sentence summary.
   On a schema-2 host only, fall back to
   `{{project_root}}/.claude/docs/subsystems/{{subsystem}}.md` and record a
   migration warning in the output; never treat both homes as independent maps.
3. `{{project_root}}/.claude/docs/workflows/{{subsystem}}.md` — the
   user-visible workflow doc, if the subsystem owns one. May not
   exist for pure-backend subsystems.
4. `{{project_root}}/.claude/docs/canonical-patterns.md` — the law as
   stated. Note if the subsystem's plumbing for this work would
   violate any pattern.
5. `{{project_root}}/.claude/docs/architectural-smells.md` — known
   smells. Note if the work would land *in* a smell-flagged file.

### Investigation procedure

#### I1. Read plan §1-2 and the subsystem doc

Form a one-sentence summary: "This work asks subsystem
`{{subsystem}}` to do X, which today it does/does-not do via Y." The
"does-not" case is important — flag it as a fork (the work may need
to add a NEW capability to this subsystem).

#### I2. Locate landing surfaces

Search the subsystem's code (and modules listed under
`integration points` in the doc, if any) for plausible landing
surfaces. Heuristics:

- Match in-scope nouns to model class names; grep their definitions +
  read sites.
- Match in-scope verbs to existing complementary verbs (e.g., "merge
  X and Y" → grep for the existing X-handling and Y-handling sites).
- For workflow-touching work, check `core/urls.py` /
  `core/api_urls.py` for relevant route families.

For each landing surface, note: file path, symbol name, and a short
anchor (`# Pagination block`). **Do not paste raw line numbers** —
they rot fast. Symbol name + anchor is durable.

#### I3. Trace blast radius for each landing surface

For every landing surface, grep for:

- **Callers** — who calls this function/view/task today?
- **Templates / JS** — does a template render this? Does any
  `static/` JS module call it via fetch?
- **Celery wiring** — if it's a task, what queue (`-Q default` /
  `-Q browser`)? Is it dispatched via `safe_dispatch`? (Bare
  `.delay()` is a violation the work must NOT introduce.)
- **Signals** — does the model fire `post_save` or `pre_delete`?
- **Tests** — find test modules that exercise this surface.

#### I4. Extract behaviors-to-preserve

The most important step. For each landing surface, capture invariants
the work MUST NOT break. Be specific — name the construct, the
reason, and what fails if it breaks:

- **Ordering invariants** — "in `CrawlJobService.start()`, `status =
  'running'` save MUST happen before the Celery dispatch, otherwise
  stale-detection misclassifies the job as abandoned."
- **Queue pinning** — "the discovery task uses `-Q browser` because
  it spawns Playwright; moving to default queue corrupts state."
- **Mixin requirements** — "the view subclasses `LoginRequiredMixin`;
  removing it bypasses auth."
- **Compiled state** — "extraction logic is read from
  `SiteConfig.extraction_recipe`, not `ExtractionConfig`.
  Editing ExtractionConfig without recompiling has no effect on
  exports."

If you don't find invariants, say so explicitly — "no implicit
invariants surfaced; behaviors are explicit in the code." That's a
valid finding.

#### I5. Note out-of-scope surfaces

If the work would impact code OUTSIDE the plan's §1 in-scope list,
list those surfaces under `## Out-of-scope impact (signal for
re-scoping)`. Do NOT include them in the main findings — they are a
signal that the orchestrator may need to re-run `/scope-feature`.

### Output contract

Write a single markdown file at `{{output_path}}` with EXACTLY this
shape:

```markdown
# Impact scout — {{subsystem}} for {{plan_name}}

## Subsystem summary
<one paragraph from I1; what does this subsystem own; how does the
plan's scope map to it>

## Findings

### Landing surfaces
- `<file>::<symbol>` — <one-line role>; callers: <count or list>
  - Templates: <path or "none">
  - JS callers: <path or "none">
  - Celery: <queue or "n/a">
  - Tests: `<test_module::TestClass::test_name>` (and any others)

### Cross-subsystem touchpoints
- `<other-subsystem>`: <reason this scout believes ANOTHER subsystem
  is also touched>; orchestrator may dispatch a second scout.

(May be empty. If the plan's scope already names this other
subsystem, that's fine. If not, this is the signal that scope is
wrong — flag it.)

## Behaviors to preserve
(Ordered. Number them E1, E2, ... so plan §4 can reference them.)

- E1: <one-sentence invariant>; reason: <why load-bearing>; impact if
  broken: <what fails>.
- E2: ...

(If none found, write "No implicit invariants surfaced.")

## Out-of-scope impact (signal for re-scoping)
<surfaces touched that fall OUTSIDE plan §1's in-scope list. Do not
include them in the main findings; they are a signal that the
orchestrator may need to re-run /scope-feature.>

(May be empty — that's the happy path.)

## Risks / smell-adjacency
- <smell-flagged file in landing surfaces, with smell name>
- <pattern-violation risk if the work lands as suggested>
- (or: "no smell-adjacency or pattern violations detected")

## Notes for the orchestrator
(1-3 sentences max. Surprises, gaps, or "this might not be the right
subsystem" callouts.)
```

### Rules you MUST respect

1. **Do not expand scope.** The plan §1 is the contract. If the work
   would impact code outside it, that's a re-scoping signal — record
   it under "Out-of-scope impact", do not silently expand.
2. **Read before claiming.** Don't infer the subsystem's
   responsibilities from its name — read the doc (or the code if no
   doc exists).
3. **No raw line numbers.** Use symbol names + short anchors.
4. **Do not pick winners on cross-cutting forks.** Forks live in plan
   §6; the scout reports impact, not fork resolutions.
5. **Do not edit production code.** Read-only. Only file you write
   is `{{output_path}}`.
6. **Keep behaviors concrete.** Vague invariants like "should be
   reliable" are useless. Every E-numbered item names a specific
   construct, a reason, and a failure mode.

Do not print the markdown to your reply. Write it to `{{output_path}}`
and respond with at most two sentences confirming the write (and one
sentence flagging anything surprising — like out-of-scope impact or a
missing subsystem doc).
