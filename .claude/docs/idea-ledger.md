# Idea ledger — Tier 1 capture

Append-only JSONL ledger for every idea that touches the project. Forward-going
capture, low friction, never deleted. Tier 2 (`pattern-library.md`) is the
curated layer that promotes from this one.

> Read this when: writing or reading `.claude/ideas/log.jsonl`; authoring or
> debugging a `track-idea` / `find-orphaned-ideas` / `extract-existing-ideas`
> skill; deciding what counts as an idea worth capturing.

## What "idea" means here

Anything that could be reused or forgotten, across any subsystem the project
contains: features, refactors, prompts, harness shapes, research probes,
workflow patterns, UX prototypes, infra tweaks, hypothesis tests. Subsystem
type is a free-form tag, not a closed enum — what counts as an "idea"
depends on the project's role in the real world.

The bar for an entry: **if I dropped this thought now, would future-me wish
I'd written it down?** If yes, write it.

The ledger is not a TODO list. It captures the *thinking*, not the work
item — a rejected idea still has a ledger entry, because the rejection's
reasoning is the lesson. The work-item view lives in `reports/BACKLOG.md`;
the ledger is upstream of it.

## Location

`.claude/ideas/log.jsonl` — one JSON object per line, sorted by `created_at`
on append. Append-only: updates emit *new* event records that reference the
original by `id`, never edit prior lines.

A companion `.claude/ideas/README.md` carries a one-page direct-reader
summary for editors that don't have the skills available.

## Record types

Three record kinds share a flat schema; the `record_kind` field
discriminates:

| Kind | Cardinality | Purpose |
|---|---|---|
| `intake` | exactly 1 per `id` | The originating capture; defines the idea |
| `event` | 0..N per `id` | State transition, marker change, edge addition, adoption note, dev-note |
| `lesson` | 0..N per `id` | Distilled learning attached to an idea |

## Intake record

```json
{
  "record_kind": "intake",
  "id": "small-kebab-slug",
  "title": "One-line summary",
  "created_at": "2026-05-13T10:30:00Z",
  "origin": "convo | plan:<path> | ADR-NNNN | AI-suggestion | spike:<branch> | TODO:<file:line>",
  "subsystem_kind": "extraction | UI | agent-loop | lint | docs | prompt-template | research | infra | workflow | ...",
  "state": "proposed",
  "outcome": null,
  "quality_markers": [],
  "feeds_into": [],
  "composes_with": [],
  "lineage_parents": [],
  "lineage_children": [],
  "superseded_by": null,
  "adoption_count": 0,
  "generalizability": null,
  "last_event_at": "2026-05-13T10:30:00Z",
  "tags": [],
  "summary": "2-5 sentence problem-fit description: what is this, why might it matter, what would success look like.",
  "hypothesis": "What we expect to be true if this idea works (skip if obvious)."
}
```

### Required vs optional

Required: `record_kind`, `id`, `title`, `created_at`, `origin`,
`subsystem_kind`, `state`, `summary`. Everything else may be absent
(`adoption_count` defaults to 0; arrays default empty; nullable fields
default null).

### `id`

Kebab-case, globally unique across the ledger, stable across the idea's
lifetime. The id is the primary key — every event and lesson references
it. Choose ids that read well three months later (`hydration-fast-path`,
not `idea-47`).

### `subsystem_kind`

Free-form tag, no closed enum. Examples by project type:
- Code-product: `extraction`, `UI`, `agent-loop`, `lint`, `infra`,
  `prompt-template`, `harness-shape`
- Workflow project: `kanban-flow`, `meeting-cadence`, `review-loop`
- Research project: `experiment-design`, `data-pipeline`, `analysis-method`

A new project picks the tags that match its subsystem topology. The
`extract-existing-ideas` skill seeds the tag vocabulary from existing
folder names and document titles.

## Event record

```json
{
  "record_kind": "event",
  "id": "small-kebab-slug",
  "event_at": "2026-05-13T14:00:00Z",
  "event_kind": "transition | marker | edge | adoption | note",
  "from_state": "proposed",
  "to_state": "in-flight",
  "outcome": null,
  "markers_added": [],
  "markers_removed": [],
  "edges_added": {"feeds_into": [], "composes_with": [], "lineage_parents": []},
  "adoption_evidence": null,
  "summary": "1-3 sentence event note."
}
```

`event_kind` is informational; multiple kinds can apply to one event
(a transition can also carry edge additions). The kind names the
*primary* change. Field semantics:

- **transition** — `from_state` / `to_state` / optional `outcome` are set
- **marker** — `markers_added` / `markers_removed` are non-empty
- **edge** — `edges_added` contains non-empty arrays
- **adoption** — `adoption_evidence` is a path / PR / ref; increments
  `adoption_count` on the intake's projected view (see *Projection* below)
- **dev-note** — a development-history observation: what was built, what
  tests were run, what was learned, what was frictional. Distinct from
  `note` so queries can filter to "show me the build history of this
  skill/idea." See *Skill meta-tracking* below.
- **note** — none of the above; just a dated comment

## Lesson record

```json
{
  "record_kind": "lesson",
  "id": "small-kebab-slug",
  "lesson_at": "2026-05-13T16:00:00Z",
  "lesson_title": "Short headline",
  "lesson_body": "Rule + why + how to apply. 2-5 sentences.",
  "generalizes_to": ["subsystem_kind_a", "subsystem_kind_b"]
}
```

Lessons survive rejection. An idea that ended `state=done outcome=rejected`
can still carry valuable lessons — that's the whole point of keeping the
ledger forever. `generalizes_to` flags subsystem kinds where this lesson
might apply elsewhere; `mature-existing-ideas` reads this when crawling
adjacent patterns.

Lessons can also live in `.claude/tasks/lessons.md` (the project-wide
diary). The ledger lesson is the *attached* version — it has an idea
context. Both can coexist; cross-link as useful.

## State machine

```
          ┌──────────────────► stalled ──────────────┐
          │                       │                  │
        proposed ──► in-flight ───┴──► done          │
                          ▲              │           │
                          └──────────────┘           │
                            (re-open via             │
                             new event)              │
                                                     │
        Any state may add or remove quality markers ─┘
        (markers are orthogonal — they do not change state)
```

States:

- **proposed** — captured, not actively being worked on
- **in-flight** — someone is actively working on it
- **stalled** — assigned by `find-orphaned-ideas` when an in-flight idea
  has no new events for N days (default 14, configurable per project).
  Not set manually
- **done** — terminal. Carries an `outcome`

Outcomes (set when transitioning to `done`):

- `adopted` — landed in the codebase / workflow
- `rejected` — tried, didn't pan out; lessons retained
- `deferred` — explicitly parked (distinct from `stalled`, which is detected)
- `harvested` — partial value extracted; often paired with `has-more-potential`
- `superseded` — replaced by a newer idea; `superseded_by` is set

Re-opening: a `done` idea can move back to `in-flight` via a new event.
The historical events stay; the state just changes again.

## Quality markers

Orthogonal to state. Multiple markers can co-exist on one idea.

- **`underdeveloped`** — the idea is real but the formulation is rough.
  Mostly used at intake when the captor wants to flag "this needs more
  thinking before someone runs with it." Auto-cleared when an event raises
  the summary's detail level (manual judgment, not detected).
- **`needs-research`** — the idea would benefit from external research
  before further work. Read by `mature-existing-ideas` to pick targets.
- **`has-more-potential`** — explicitly more value remains than has been
  extracted. Set when an idea is `harvested` but the captor judges that
  remaining capacity is meaningful. Read by `find-orphaned-ideas` in
  `harvest-opportunity` mode.

Markers are additive metadata. They do not gate workflow; they steer
attention.

## Skill meta-tracking

Skills are first-class ideas in this ledger. The convention:

- **`subsystem_kind: skill`** — the idea *is* a skill (its SKILL.md plus
  any libraries it owns). Use this for every skill in `.claude/skills/`
  that is worth tracking — which, by default, is all of them.
- **`dev-note` event kind** — captures development history: what was
  built in this iteration, what tests were run, what was learned, what
  was frictional. Multiple dev-notes per skill across its lifetime; the
  chronological projection IS the skill's development history.
- **Friction** is tracked two ways depending on shape:
  - Brief friction observation → `dev-note` event with `summary` prefixed
    `friction:` (e.g. `"friction: the SKILL.md prompt needed three
    revisions before agents reliably picked the right helper."`)
  - Distilled friction lesson → `lesson` record. The `generalizes_to`
    field flags other subsystem kinds where the lesson may apply.
- **Spec conformance** — adoption events for a skill carry
  `adoption_evidence` that points at the artifact that demonstrates the
  skill working (a passing harness scenario, a real-world output, a
  reviewed run). Skill `adoption_count` is therefore a count of
  *demonstrated correct runs*, not just shipped code.

### Open gap: agentic spec-conformance validation

The harness at `.claude/tests/ideas/run_harness.py` validates the
*deterministic library* (`ideas_lib.py`) — Python functions with known
inputs and expected outputs.

It does **not** validate the *agentic part* of a skill — whether the
SKILL.md prompt drives an AI agent to consistently produce the output
the spec promises. This is a known gap, captured as ledger entry
`skill-spec-conformance-validation` with markers `[underdeveloped,
needs-research, has-more-potential]`. When that idea matures into a
skill, this section should cross-link to it.

Until then, skill spec conformance relies on:

- Manual review of a small number of runs against the harness fixtures
  the deterministic library covers
- Reviewer judgment when a new skill is wired into a real workflow
- `mature-existing-ideas` flagging skills that have not had recent
  research / re-validation

## Edges (composability)

Three first-class edge fields enable composable-idea queries:

- **`feeds_into[]`** — this idea is a building block of a larger composite
  idea. Forward edge.
- **`composes_with[]`** — sibling ideas that work together. Symmetric edge.
- **`lineage_parents[]`** — ideas this is an evolution / remix of. Back
  edge; `audit-ideas` reconciles `lineage_children` from these.

Queries the edges enable:

1. *"What composite ideas would this small idea contribute to?"* — follow
   `feeds_into` forward.
2. *"What ideas compose with this one?"* — follow `composes_with`
   sideways.
3. *"What's the evolution chain leading to this idea?"* — follow
   `lineage_parents` backward, `lineage_children` forward.

Edges are not transitive in storage. `query-patterns` may compute closures
on read.

## Adoption and generalizability

`adoption_count` is a *projected* field — the canonical source is the
count of `event` records with non-null `adoption_evidence` for this `id`.
Consumers may cache this on a derived view; the ledger itself stores
events, not the count.

The first adoption (`adoption_count == 1`) is the **promotion gate** for
Tier 2. Single use validates "value for at least one set of constraints,
even if not yet generalizable."

`generalizability` lives on the Tier 2 pattern entry, not the ledger. The
ledger tracks adoptions; the pattern records the qualifier:

- `single-constraint-set` — 1 adoption
- `validated-across-N` — 2-3 adoptions across distinct contexts
- `broadly-applicable` — 4+ adoptions across distinct contexts

`audit-pattern-library` upgrades the qualifier as evidence accumulates.

## Worked example — three records for one idea

```jsonl
{"record_kind":"intake","id":"hydration-fast-path","title":"Use __NEXT_DATA__/__NUXT_DATA__ as extraction fast path","created_at":"2026-04-18T09:12:00Z","origin":"convo","subsystem_kind":"extraction","state":"proposed","outcome":null,"quality_markers":["has-more-potential"],"feeds_into":[],"composes_with":["json-ld-fallback"],"lineage_parents":[],"lineage_children":[],"superseded_by":null,"adoption_count":0,"generalizability":null,"last_event_at":"2026-04-18T09:12:00Z","tags":["hydration","next-data","fast-path"],"summary":"SSR frameworks ship pre-hydration JSON in __NEXT_DATA__ / __NUXT_DATA__. Often richer than JSON-LD and available at basic tier. Could short-circuit the AI-extraction loop for sites that hydrate.","hypothesis":"For SSR sites, 60-80% of fields can be lifted from hydration data without invoking the extraction agent."}
{"record_kind":"event","id":"hydration-fast-path","event_at":"2026-04-25T11:00:00Z","event_kind":"transition","from_state":"proposed","to_state":"in-flight","outcome":null,"markers_added":[],"markers_removed":[],"edges_added":{},"adoption_evidence":null,"summary":"Picked up; prototyping detector under app/services/extraction_compiler/."}
{"record_kind":"event","id":"hydration-fast-path","event_at":"2026-05-09T15:30:00Z","event_kind":"adoption","from_state":null,"to_state":null,"outcome":null,"markers_added":[],"markers_removed":["has-more-potential"],"edges_added":{},"adoption_evidence":"app/services/extraction_compiler/hydration_fast_path.py","summary":"Landed; covers Next.js and Nuxt. Marker cleared because the full hypothesis is now tested."}
```

The projection of the three records: `state=in-flight`,
`adoption_count=1`, `markers=[]`, `last_event_at=2026-05-09T15:30:00Z`.
Eligible for Tier 2 promotion.

## Projection

Tools that read the ledger compute a *projection* per `id`: the intake
record overlaid with every event in chronological order, plus an
`adoption_count` from event records carrying `adoption_evidence`, plus
the union of all attached `lesson` records.

Projection rules:

- `state` = latest event with non-null `to_state`, else intake's `state`
- `outcome` = latest event's `outcome` if `to_state == "done"`, else null
- `quality_markers` = intake's set, then apply every event's
  `markers_added` / `markers_removed` in chronological order
- `feeds_into` / `composes_with` / `lineage_parents` = intake's set unioned
  with every event's `edges_added.<field>`
- `adoption_count` = count of events with non-null `adoption_evidence`
- `last_event_at` = max(intake.created_at, max event_at across events)

Projection is the read model; the ledger is the write model.

## How the skills interact with the ledger

| Skill | Writes | Reads |
|---|---|---|
| `track-idea` | intake, event, lesson | projection (to validate input) |
| `find-orphaned-ideas` | event (stall transitions, marker assignments) | projection + filesystem scan |
| `extract-existing-ideas` | intake (bulk), lesson | filesystem + git + memory + plans |
| `brainstorm-ideas` | intake (bulk, in `proposed` state) | external (web, AI ideation) |
| `mature-existing-ideas` | event (research-log notes), lesson | Tier 2 patterns + external research |
| `audit-ideas` | event (lineage reconciliation, stale-flag transitions) | projection across full ledger |
| `query-patterns` | nothing | Tier 2 patterns only (rarely projection) |
| `promote-idea-to-pattern` | nothing in ledger | projection; writes Tier 2 file |

Direct manual edits to the JSONL are allowed but skills carry validation —
prefer the skills.

## Audit and integrity

`audit-ideas` runs on demand or scheduled:

- Reconcile `lineage_parents` → `lineage_children` back-pointers
- Verify every `superseded_by` resolves to an existing id
- Flag in-flight ideas with `last_event_at` older than N days; emit a
  transition event moving them to `stalled`
- Flag Tier 2 patterns whose source ledger entry has been superseded
- Flag intake records with `subsystem_kind` not seen elsewhere (likely
  typo; manual confirmation)
- Report orphan-detection candidates per `find-orphaned-ideas` modes

Output: `reports/audit-ideas/audit-<TS>.json` plus a console summary.
Findings are advisory; no auto-write to ledger except the explicit
stale-flag transition (governed by a confirmable flag).

## What NOT to put in the ledger

- Bug fixes with no design content — go in commit messages
- One-off implementation details — `lessons.md` if anywhere
- Conversation transcripts — link the ledger entry to the conversation
  artifact rather than copying it in
- Secrets, credentials, API keys — never. The ledger is checked in.

## Cross-references

- Tier 2 format: `pattern-library.md`
- Inline query template: `query-patterns-inline.md`
- ADR motivating this system: `ai-docs/decisions/0013-idea-tracking-system.md`
- Direct-reader summary: `.claude/ideas/README.md`
