# Architectural smells — what to look for, what they cost

Duplication and dormancy are the easy failure modes — you can find them
with lexical and reachability analysis. The harder ones are
**architectural smells**: code that is neither duplicated nor dead, but
where a single name carries too many concepts, or an implicit contract
lives in someone's head. Scans miss them; humans feel them as
"suspicious progress" and "haunted files."

Nine smells concern us in this ecosystem. Each has a SUSPECT detector
(`/find-*` skill) and an EXPLAIN contract-maker (`/extract-*`,
`/introduce-*`, or `/propose-*` skill). The canonical terminology below
is what every skill, lint rule, and canonical-pattern entry refers back
to.

Host projects extend the catalogue with their own domain-specific smells
as `/prevent-regression` lands new lints. The seed list here covers the
language- and framework-agnostic shapes — duplication, stringly state,
read-named writes, layer violation, format-equivalence gaps, product-
topology drift, frontend primitive bypass, folder-topology drift, and
missing boundary.

## Backref convention — `Decided in: NNNN`

When a smell entry corresponds to an Architectural Decision Record
under `ai-docs/decisions/`, the entry should carry a `Decided in: NNNN`
line near its detector/refactor metadata, pointing at the ADR id. This
turns the smells doc from a flat list into a graph — readers can follow
the link to recover the rejected alternatives, the consequences, and
the supersession chain.

When `/decide` writes an ADR with `related_smell: <anchor>` in
frontmatter, the skill recommends adding the matching backref here —
the human applies it (auto-edits to this file are not allowed). The
`scripts/decisions.py link-check` command verifies that every
`related_smell` in an ADR has a matching `Decided in:` here, and flags
missing pairs.

## 1. Omnibus module

**Shape.** A single file answers questions from three or more domains.
The SRP sentence test ("this file handles X **and** Y **and** Z")
counts three or more "and"s where each "and" joins independently-
understandable domains.

**What it costs.** Readers can't hold the file in one pass. Edits
require understanding three domains to change one. AI agents appear to
understand the file while missing the real contract.

**Detector.** `/find-omnibus` — SRP "and" test + cluster-
count-times-LOC ranking.

**Contract-maker / refactor.** Three options, framed by recency and
local pain — don't default-frame this as "to refactor or not":

- **Decompose** — `/refactor-subsystem` with `decomposition` mode
  splits by responsibility cluster into a directory package with a
  thin re-export `__init__.py`. Right when the domains are genuinely
  independent and edits to one keep triggering test work on the
  others.
- **Reorganize in place** — `/organize-file` (future skill — intake
  `organize-file-skill`) clusters symbols by domain, adds banner
  comments + a top-of-file index, declares `__all__`; **zero semantic
  changes**. Right when the file is large but cohesive enough that
  decompose-cost > readability-win.
- **Leave alone** — if the file hasn't been edited in 90+ days, the
  archaeology cost of any reorg outweighs the readability win. A
  `--require-recent-edits` gate enforces this by default; `--force`
  is the explicit override.

Pairs with `ai-docs/decisions/0017-staged-boundary-rearchitecting.md`
when the decompose option's blast radius forces phasing.

## 2. Stringly-typed state / tuple-inferred identity

**Shape.** State lives in bare string literals (`"pending"`,
`"in_progress"`, `"failed"`) with no typed enum (`TextChoices`,
`StrEnum`, etc.), OR identity is inferred from
`(status, timestamp, nullness)` tuples instead of a real foreign key.

**What it costs.** IDEs don't know the valid values. A typo in
`"in_porgress"` produces silent no-op comparisons. Identity tuples
break under race conditions (two jobs with overlapping timestamps).
Schema changes can't find all callers.

**Detector.** `/find-implicit-state` — AST scan for
repeated string-literal comparison against `.status` / `.phase` /
`.state`, plus `.filter(status=..., created_at__gt=...)` patterns.

**Contract-makers / refactor.**
- `/extract-enum` — propose typed enum + caller migration.
- `/introduce-fk` — propose FK + data migration (backfill + set-NOT-NULL
  two-step).

**Decided in:** 0001 (TextChoices for state).

## 3. Query mutation

**Shape.** A method whose name promises "read" (`get_*`, `fetch_*`,
`load_*`, `list_*`, `find_*`, `check_*`) actually mutates — `.save()`,
`.delete()`, `.update_or_create()`, or attribute assignment on
persisted objects.

**What it costs.** Callers trust the name. A read path that writes
creates race conditions, unexpected history entries, and makes the
system untestable without spinning up the full DB. Debugging feels
haunted — log lines show "fetch" but the row changed.

**Detector.** `/find-query-mutation` — AST scan for
read-named functions whose bodies contain mutation calls. Allow-list
via `# hidden-mutation: <reason>` docstring/comment with non-empty
reason.

**Refactor.** Rename to `get_or_create_*`, `fetch_and_heal_*`,
`touch_*`, etc.; OR split into a pure reader + a separate mutator.

## 4. Layer violation

**Shape.** A view function or a Celery task owns business logic that
belongs in a service. Symptoms: domain loops, direct LLM calls,
dispatch helpers bypassed, multi-model DB transactions, more than a
few hundred LOC per view.

**What it costs.** Tests require HTTP request factories when they
should require service calls. Reuse across callers (Celery task +
management command + view) becomes copy-paste. Logic can't be
exercised headlessly.

**Detector.** `/find-layer-violation` — AST scan for views/tasks
containing business-logic shapes (domain loops, LLM calls, dispatches
outside the canonical wrapper, multi-model transactions).

**Refactor.** Extract service module and reduce the view/task to a
thin wrapper that parses the request, calls the service, returns a
response.

## 5. Format-equivalence gap

**Shape.** Two or more code paths produce conceptually-equivalent
output on shared inputs (same model rows, same dict shape, same
export columns) without routing through a canonical producer. One
path silently drifts on a guard (validation, normalization, mapping,
freshness gate, queryset filter) while another runs it correctly.
Discriminator: would a characterization test be able to assert that,
on the same input, both paths produce identical output? If yes, they
are parallel writers of the same output shape.

**What it costs.** Silent divergence on guards. The non-guarded path
produces invalid data (malformed URLs, wrong mappings, stale cache
hits, unfiltered exports). Tests on the canonical path pass; the
parallel path's bug only surfaces in production at the divergent
caller. Reviewers miss it because the structural similarity is high —
small key/value differences pass casual review.

**Detector.** `/find-semantic-duplication` surfaces parallel-writer
clusters as semantic candidates. No general AST detector exists; the
shape requires comparing output structure across paths, not token
similarity.

**Contract-maker / refactor.** `/fix-workflow share_utilities`
shape — extract a canonical producer (helper, service method,
queryset builder) that holds the guard, then route every parallel
writer through it. When extraction would violate interface depth
(transport adapters, library-specific ports, cross-DB connectors with
different driver semantics), use `keep_separate_document_why`
sibling-pointer docstrings instead. The interface-depth gate
(`.claude/skills/_common/interface-depth.md`) decides which.
`/prevent-regression` can ship per-shape AST lints after a recurring
instance justifies one.

**Decided in:** 0004 (parallel writers shared helper).

## 6. Product-topology drift

**Shape.** A user-visible workflow is coherent in the product but not
coherent in code. Routes, views, templates, JavaScript boot globals,
status providers, and docs each carry their own copy of step knowledge.

**What it costs.** New engineers can understand the product but cannot
find the single owner of a workflow step. Refactors fix one layer while
leaving another stale. Docs and frontend globals become invisible public
contracts.

**Detectors.**
- `/find-route-sprawl` — flat route ownership, missing include
  boundaries, duplicate alias surfaces.
- `/find-workflow-duplication` — repeated step labels, tab IDs, route
  literals, and workflow definitions.
- `/find-frontend-contract-drift` — template globals and JS read drift.
- `/find-doc-route-drift` — documented route/redirect drift.

**Contract-maker / refactor.** `/extract-workflow-registry` proposes the
canonical registry. `/refactor-subsystem` or `/fix-workflow` executes it
after characterization tests. `/prevent-regression` can later guard
route ownership and boot-payload conventions.

## 7. Frontend primitive bypass

**Shape.** A canonical UI primitive exists (a Cotton component, React
component, partial, or shared JS helper) but call sites still hand-roll
the same shell — a copy of the CSS class chain, a parallel JS helper
with a drifted body, an inline CSRF fetch wrapper, etc. The primitive's
existence is invisible to the agent that wrote the new page, so each
new surface re-derives the same shape from first principles. The
discriminator: would running the existing primitive at the call site
produce the same rendered DOM or the same network behavior, modulo
whitespace? If yes, the call site is bypassing the primitive.

**What it costs.** Visual drift is invisible at PR-review time — the
migration to a new tone, padding, or border style only flips the
adopting callsites, leaving the bypassers stale. JS helper forks drift
silently: the imported helper gets a security fix; the inlined copy
doesn't. CSRF wrapper gaps mean a per-request opt-in to behavior the
platform already standardizes (retry, timeout, error toast). And once a
fork lands, the next AI agent sees N versions and can't tell which is
canonical — duplication compounds duplication.

**Detector.** `/find-frontend-duplication` — three deterministic
scanners (primitive inventory, class-chain tone-normalization, JS helper
fork detector) feed a collapse stage that classifies clusters and flags
`primitive_bypass: true` when an existing primitive covers the cluster.

**Contract-maker / refactor.**
- `/extract-cotton-primitive` — proposes the primitive's shape,
  variable declarations, JS partner, and before/after migration table
  for every callsite the profile loaded.
- For JS helper forks, `/fix-workflow share_utilities` extracts the
  canonical helper and migrates callers.
- `/prevent-regression` lands a per-shape lint once the primitive is
  adopted, so the next AI-grown page can't reintroduce the bypass.

## 8. Folder topology drift

**Shape.** A directory's layout no longer matches the cluster shape it
contains. Two directions, same threshold (N≥3 = pattern):

- **Promotion overdue.** A flat directory accumulates N≥3 modules
  sharing a `<prefix>_` token (`views/site_config_*.py`,
  `tasks/extraction_*.py`) — the cluster names a domain but the file
  layout still treats each member as an unrelated singleton. New AI
  agents writing the next sibling don't see the cluster; they add an
  N+1th file and the junk drawer grows.
- **Demotion overdue.** A folder package's source-module count has
  fallen below N=3 — files merged, deleted, or moved out, but the
  `__init__.py` and the directory wrapper persist. Packaging that was
  once earned now adds navigation cost without a cluster to justify
  it. The discriminator is bidirectional: clusters earn packaging at
  ≥3 siblings AND lose it below ≥3.

**What it costs.** Junk-drawer flatness destroys the "skim and
locate" property of a directory listing — the reader has to grep file
names to recover the cluster. Sparse packages cost the inverse:
forced indirection through a folder + `__init__.py` for content that
would read more directly as a flat sibling. Either way, the layout
lies about the code's structure, and the next AI agent extends the
lie because the existing pattern is what it imitates. The deeper
rule under both directions — *framework norms are a floor; above
that floor, maximally prioritize intuitiveness and skim-to-find* —
is in `.claude/skills/_common/structural-design-principles.md`.

**Detector.** `/find-folder-topology-drift` — three Stage 1 bands
(`flat_prefix_cluster`, `tests_by_prefix`, `sparse_folder_package`).
Framework-mandated folders (`migrations/`, `management/`, `commands/`,
`templatetags/`, `fixtures/`, `tests/`) are exempt from demotion.

**Contract-maker / refactor.**
- `/propose-folder-reorganization <cluster-id>` — emits per-cluster
  proposal: current → proposed tree, file-move table, import-impact
  summary, characterization-test matrix, migration sequencing,
  stop condition. Two modes: promote (flat → folder) and demote
  (folder → flat).
- `/refactor-subsystem` (decomposition mode) executes the proposal
  under ADR 0002's spec-first, two-commit discipline. One cluster
  per PR.
- A future `/prevent-regression` lint could enforce the threshold
  against future PRs once the convention's recurrence rate justifies
  it. Deferred for now — the SUSPECT/EXPLAIN/REFACTOR loop is
  enough until drift is measurable post-cleanup.

**Decided in:** 0006 (folder-organization). The bidirectional Rule 5
that pairs the demote direction with the promote direction is
explicit there, not derivable from the threshold alone — packaging
is earned, and the loss path is the symmetric counterpart.

## 9. Missing boundary

**Shape.** The inverse of smell 1. Distinct domain concerns live in
separate files in the same package, but with no defined public contract
between them — sibling modules import each other's private helpers,
share mutable state, or co-evolve such that a change in one always
touches the others. No public-surface declaration (`__all__`, explicit
re-export list, interface protocol) narrows what callers may reach for;
deep relative imports cross what should be a boundary; tests for X also
need Y and Z set up; the same identity gets used as several different
things. The SRP "and" test fails one level down: each file looks
coherent in isolation, but the *package* answers questions from three
or more domains and the boundary between them is implicit.
Discriminator: if you tried to extract one sibling into its own package
today, how many private-helper imports and shared-mutable-state
references would break? If the answer is "more than the public surface
advertises," the boundary is missing.

**What it costs.** Refactor paralysis — you can't change one cluster
without audit-grepping all callers. Test setup explosion — exercising
one cluster requires fixturing the others. Concept fighting — readers
keep re-discovering an unwritten coupling contract, and the next AI
agent extends it because the existing pattern is what it imitates.
Distinct from smell 1 (omnibus): the *file* may already be split; what
is missing is the *interface*.

**Detector.** `/propose-boundary` — read-only structured-proposal pass
that scores symbol pairs by co-edit frequency, mutual import
directionality, naming alignment, and cross-cluster call-edge density.
Can also be hinted by `/map-subsystem` Stage 4 dep-graph output
(low-density inter-cluster edges with high-density intra-cluster
edges).

**Contract-maker / refactor.** `/propose-boundary` produces the
proposal (cluster contents, proposed public API, backward-compat shim
shape, characterization-test matrix). `/refactor-subsystem` executes
it. Pairs with `ai-docs/decisions/0017-staged-boundary-rearchitecting.md`
(template ADR — adopters calibrate the N thresholds per project) for
the when-to-phase decision framework.

**Decided in:** 0017 (staged-boundary-rearchitecting, template).

## How the skills compose

For any smell:

1. **SUSPECT** — the `/find-*` skill surfaces candidates.
2. **EXPLAIN** — `/explain-code` or the contract-maker skill writes the
   hidden contract down.
3. **REFACTOR** — `/fix-workflow` or `/refactor-subsystem` executes.
4. **GUARD** — `/prevent-regression` installs the lint rule so the
   same smell can't land again.

The REFACTOR step uses spec-driven, two-commit, characterization-test
discipline. **Decided in:** 0002 (spec-first refactor).

See `.claude/docs/skill-catalog.md` for the full catalog organized by
job.

## Canonical Patterns this file pairs with

`canonical-patterns.md` pins the positive form of each smell as a
catalogue entry the host project's `/prevent-regression` lints
reference:

- **Status fields use typed enums** — negative form of smell 2
  (stringly-typed state).
- **Query methods are side-effect free** — negative form of smell 3
  (query mutation).
- **Job identity is an explicit FK** — negative form of smell 2's
  tuple-inferred-identity sub-shape.
- **Views and tasks are thin HTTP/dispatch wrappers** — negative form
  of smell 4 (layer violation).
- **Parallel writers route through a shared producer** — negative form
  of smell 5 (format-equivalence gap).
- **Product workflows have one registry** — negative form of smell 6
  (product-topology drift).
- **Frontend primitives — three callsites across two templates**
  threshold — negative form of smell 7 (frontend primitive bypass).
