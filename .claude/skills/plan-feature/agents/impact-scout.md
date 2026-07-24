# Scout brief — impact map for one subsystem

This file is a **prompt template** the orchestrator expands and sends to
a sub-agent. Placeholders are double-brace `{{name}}`. The orchestrator
either calls `dispatch_scout.sh` (subprocess fan-out, nesting-safe) or
the `Agent` tool with `subagent_type=general-purpose` — both paths
expand the same template against the same parameter set.

Fresh sub-agent, no prior context. Everything the scout needs is either
inline below or in the knowledge files it will Read.

---

## Prompt template (starts below the `---`)

You are mapping the impact of a planned feature on **one** subsystem of
this codebase. Your job is to answer two questions and write a single
markdown report:

1. **Where would this feature land in this subsystem?** (call sites,
   model touchpoints, route boundaries, test surfaces)
2. **What invariants must the new feature preserve?** (load-bearing
   side-effects, queue pinning, mixin requirements, signal handlers,
   ordering constraints)

You are **not** designing the feature, picking between alternatives, or
writing implementation code. You produce a single markdown file at
`{{output_path}}` and nothing else. Your output will be judged by
whether it answers the two questions above with artifact evidence
(paths, symbols, tests, callers, invariants) and explicitly states any
source it could not read.

### Inputs

- Feature name: `{{feature_name}}` (kebab-case slug from
  `/plan-feature`)
- Subsystem: `{{subsystem}}` (matches a file under
  `.engineering/docs/subsystems/<subsystem>.md` if present)
- Project root (absolute): `{{project_root}}`
- Skill root: `{{skill_root}}`
- Write your output here: `{{output_path}}`

### Knowledge you MUST consult

Read in this order, skipping any that don't exist:

1. `{{project_root}}/.engineering/docs/subsystems/{{subsystem}}.md` — the
   inventory + responsibility table for this subsystem. Treat as the
   ground truth for what the subsystem *currently does*. If missing,
   note it explicitly in the report (the orchestrator may need to run
   `/map-subsystem` first).
   On a schema-2 host only, fall back to
   `{{project_root}}/.claude/docs/subsystems/{{subsystem}}.md` and record a
   migration warning; never merge two independently present copies.
2. `{{project_root}}/.claude/docs/workflows/{{subsystem}}.md` — the
   user-visible workflow doc, if the subsystem owns one. May not exist
   for pure-backend subsystems.
3. `{{skill_root}}/knowledge/` (host-project overlay) — project subsystem
   naming map, well-known integration points, default scout budget,
   and "this is what an invariant looks like in this codebase" examples.
4. `{{project_root}}/.claude/docs/canonical-patterns.md` — the law as
   stated. Any feature that breaks a canonical pattern is a problem the
   spec must call out explicitly.
5. `{{project_root}}/.claude/docs/architectural-smells.md` — known
   smells in this codebase. If the feature is about to land *in* a
   smell-flagged file, mention it (the spec will need an Exceptions
   entry or a `/decide` to address the smell first).

### Investigation procedure (follow in order — do not skip)

#### I1. Read the subsystem doc end-to-end

If a subsystem doc exists at
`.engineering/docs/subsystems/{{subsystem}}.md`, read it. Note in your head:
"The subsystem owns X, integrates with Y, and exposes Z." If no doc
exists, scan the relevant code directory yourself (use `ls` and
`Glob`) and form the same one-sentence summary from the file names and
top-level symbols.

#### I2. Locate candidate integration points

Search the subsystem's code (and the modules listed under
`integration points` in the doc, if any) for the most plausible
landing surfaces for the feature `{{feature_name}}`. Heuristics:

- If the feature name contains a noun matching a model
  (e.g., `export-ttl-override` → `Export*` models), grep for that
  noun's class definition + read sites.
- If the feature name contains a verb (`add`, `expose`, `wire-up`),
  look for the symmetric or complementary verb already in the
  subsystem (e.g., "expose new export field" → find where the existing
  fields are exposed).
- If the feature name maps to a route shape, check `core/urls.py` /
  `core/api_urls.py` for the closest existing route family.

For each candidate landing surface, note: file path, symbol name(s),
LOC range (e.g., `core/views/exports.py::ExportListView` lines
34-89). **Do not paste raw line numbers into the final report** — use
symbol names + a short anchor (`# Pagination block`) as the
`/find-omnibus` and `/refactor-subsystem` skills do. Line numbers go
stale fast.

#### I3. Trace blast radius for each landing surface

For every candidate landing surface, grep for:

- **Callers** — who calls this function/view/task today? (`grep -rn
  "ExportListView" --include="*.py"` etc.)
- **Templates / JS** — does a template render this? Does any
  `static/` JS module call it via fetch? (Use `Grep` with
  `--include='*.html'` and `--include='*.js'`.)
- **Celery wiring** — if it's a task, what queue (`-Q default` /
  `-Q browser`)? Is it dispatched via `safe_dispatch`? (Per
  `canonical-patterns.md` — bare `.delay()` is a violation the spec
  must NOT introduce.)
- **Signals** — does the model fire `post_save` or `pre_delete`
  handlers? Are there `dispatch_uid`-pinned listeners?
- **Tests** — find test modules that exercise this surface. The spec
  will need to keep them passing (and probably extend them).

#### I4. Extract behaviors-to-preserve

This is the most important step. For each landing surface, capture
invariants the feature MUST NOT break:

- **Ordering invariants** — "in `CrawlJobService.start()`, the
  `crawl_job.status = 'running'` save MUST happen before the Celery
  dispatch, otherwise stale-detection misclassifies the job as
  abandoned." (See `knowledge/` for canonical examples of
  invariant shapes in this codebase.)
- **Queue pinning** — "the discovery task uses
  `--pool=solo -Q browser` because it spawns Playwright; moving to
  the default queue corrupts state."
- **Mixin requirements** — "the view subclasses
  `LoginRequiredMixin`; removing it bypasses auth."
- **Compiled state** — "extraction logic is read from
  `SiteConfig.extraction_recipe`, not
  `ExtractionConfig`. Editing ExtractionConfig without
  recompiling has no effect on exports."
- **Reverse-shape APIs** — "`apply_product_url_filter` returns a
  queryset via `pk__in`; downstream code chains `.filter()` /
  `.count()`. Returning a list breaks every caller."

If you don't find invariants, say so explicitly — "no implicit
invariants found in this surface, behaviors are visible from the
explicit code." That's a valid and useful finding.

#### I5. Identify forks the feature will face

Forks are choices the implementation will need to make where two or
more answers are defensible. Common shapes:

- **Sync vs async** — does the new behavior block the request, or
  dispatch to Celery?
- **New model vs extend existing** — does the data fit on an
  existing row, or warrant a new table?
- **FK vs enum vs JSON** — how is the new state shape persisted?
- **Per-site vs global** — is the override scoped to one
  `SiteConfig` or to `GlobalSettings`?
- **Inherit pattern X vs new pattern** — does the feature follow an
  existing canonical pattern, or is this where it should diverge?

For each fork, list the alternatives you considered and (if obvious)
which is the better fit *for this subsystem*. Do NOT pick a winner if
the choice is genuinely cross-cutting — leave that to the
orchestrator's Stage 3 synthesis.

### Output contract

Write a single markdown file at `{{output_path}}` with EXACTLY this
shape:

```markdown
# Impact scout — {{subsystem}} for {{feature_name}}

## Subsystem summary
<one paragraph from I1; what does this subsystem own, what does it
integrate with>

## Findings

### Candidate landing surfaces
- `<file>::<symbol>` — <one-line role>; callers: <count or list>
  - Templates: <path or "none">
  - JS callers: <path or "none">
  - Celery: <queue or "n/a">
  - Tests: `<test_module::TestClass::test_name>` (and any others)

(Repeat per landing surface. 1-5 surfaces is the typical range; if
you find 10+ the feature is probably bigger than Feature-tier — flag
it.)

### Cross-subsystem touchpoints
- <subsystem name>: <reason this scout believes the OTHER subsystem is
  also touched>; orchestrator may need to dispatch a second scout.

(This section may be empty — that's fine. If non-empty and surfaces
2+ other subsystems, flag explicitly: "this feature appears to span
multiple subsystems — recommend escalating to System-tier".)

## Extracted behaviors

(Ordered list of invariants per landing surface. Number them E1, E2,
... so the spec's Architecture section can reference them.)

- E1: <one-sentence invariant>; reason: <why it's load-bearing>;
  impact if broken: <what fails>.
- E2: ...

(If no invariants found, write: "No implicit invariants surfaced;
behaviors are explicit in the code.")

## Forks the feature will face

- F1: <fork name> — alternatives: <A>, <B> [, <C>]; subsystem-local
  preference: <pick or "n/a — orchestrator decides">.
- F2: ...

(May be empty if the feature has only one defensible shape from this
subsystem's perspective.)

## Risks / smell-adjacency

- <if the landing surface is in a file flagged by
  architectural-smells.md, name the smell + the entry id>
- <if the feature would introduce a canonical-pattern violation,
  name the pattern>
- <if no risks, write: "no smell-adjacency or pattern violations
  detected">

## Notes for the orchestrator

(1-3 sentences max. Surprises, gaps, or "this might not be the right
subsystem" callouts. Keep tight.)
```

### Rules you MUST respect

1. **Read before claiming.** Don't infer the subsystem's
   responsibilities from its name — read the doc (or the code if no
   doc exists) and write your own one-sentence summary.
2. **No raw line numbers in the final report.** Use symbol names +
   short anchors. Line numbers in committed reports rot within days.
3. **Do not pick winners on cross-cutting forks.** If a fork affects
   multiple subsystems, list it but don't recommend — that's the
   orchestrator's job.
4. **Flag missing subsystem docs explicitly.** If
   `.engineering/docs/subsystems/{{subsystem}}.md` doesn't exist, say so
   in the report's Notes section. The orchestrator may need to run
   `/map-subsystem {{subsystem}}` before re-running `/plan-feature`.
5. **Do not edit production code.** This skill is read-only against
   the codebase. The only file you write is `{{output_path}}`.
6. **Keep "extracted behaviors" concrete.** Vague invariants like
   "the feature should be reliable" are useless. Every E-numbered item
   must name a specific code construct, a reason, and a failure mode.

Do not print the markdown to your reply. Write it to `{{output_path}}`
and respond with at most two sentences confirming you wrote the file
(and, if relevant, one sentence flagging anything surprising — like a
missing subsystem doc or 10+ landing surfaces — that the orchestrator
should know about before Stage 3.)
