# Portability roadmap for `_common/`

The skill ecosystem was originally Django-flavored because that is what the seed
host project needed. The language-level family now has bounded coverage across
13 expansion languages; the exact current truth lives in the generated
capability matrix and per-language coverage files. This roadmap is about a
possible shared core/language/framework/repository content layout, not about
whether those language outcomes exist. Cross-framework reuse remains future
work. The document pins the layering rule so later changes do not accidentally
cement one host's assumptions into shared files.

**Status:** roadmap, not a plan-of-record. The full reorg is reconsidered when
a non-Django host project starts adopting these skills, or when a genuinely
portable skill needs a clean `_lib/core/` import path.

---

## Why this matters

A senior engineer crossing into a new project should not have to re-derive
the skill ecosystem's affordances. For validated-neutral skills, language and
framework should be execution details; deliberately stack-bound skills must
keep their coupling explicit. Today, that distinction is muddled — shared
content can mix "every skill follows this report layout" (project-agnostic)
with "use `.venv/bin/python`" (Python-specific) with host-project-specific test
commands.

Completed language cohorts solve this selectively through language-local
providers and explicit on-demand closures, but a new cross-family
implementation can still need to re-explain the same report layout. A new
Django-but-different-domain project would likewise need to re-explain the same
Python conventions. A later split may remove that friction if its measured
benefit outweighs the migration cost.

## The four-layer split

```
_lib/
├── core/           # Project-agnostic, language-agnostic
├── language/
│   ├── python/     # Python-specific, project/framework-agnostic
│   └── <language>/ # added only when shared content earns this layer
├── framework/
│   ├── django/     # Django-specific, project-agnostic
│   ├── fastapi/    # (future)
│   └── none/       # CLI tools, scripts, libraries
└── repo/
    └── <host>/     # The host project specifically
```

**Ownership rule:** content lives in the most-general layer that still
makes the rule true. A rule that's only true under Django goes under
`framework/django/`. A rule that's true for any Python project goes
under `language/python/`. A rule that's true regardless of language
goes under `core/`.

**Layering:** `framework/<fw>/` files may reference `language/<lang>/`
files; `language/<lang>/` files may reference `core/` files. The
reverse is forbidden — `core/` cannot reference `language/python/`
because that would defeat the portability guarantee.

## What moves where (eventual plan)

| Today | Eventual destination |
|---|---|
| `_common/skill-conventions.md` | `_lib/core/skill-conventions.md` |
| `_common/skill-frontmatter.md` | `_lib/core/skill-frontmatter.md` |
| `_common/interface-depth.md` | `_lib/core/interface-depth.md` |
| `_common/structural-design-principles.md` | `_lib/core/structural-design-principles.md` |
| Host-project-specific Python conventions | `_lib/language/python/conventions.md` |
| Host-project-specific Django conventions | `_lib/framework/django/conventions.md` |
| Host-project-specific repo overlays | `_lib/repo/<host>/specifics.md` |
| `_common/dispatch_scout.sh` | `_lib/core/dispatch_scout.sh` (shell-only, no language coupling) |
| `_common/portability-roadmap.md` | `_lib/core/portability-roadmap.md` (this file) |

Skills under `.claude/skills/<name>/` reference the layer files they
need. A Python+Django+host-specific skill reads all four layers; a
portable skill reads only `core/`.

## Rules for new content before the split lands

When adding a shared convention, decide which **future** layer it would
live in:

- Future `_lib/core/` content → write to `_common/skill-conventions.md`.
- Future `_lib/language/python/`, `_lib/framework/django/`, or
  `_lib/repo/<host>/` content → write to a sibling host-overlay file
  (`<host>-specifics.md` next to `skill-conventions.md`).
- If you can't tell, default to the host overlay (over-specific is
  reversible; over-general bakes in assumptions that are expensive to
  undo later).

Never copy content from one file into the other "for convenience." The
split exists because duplicated content drifts; if the same rule needs
to appear in both files, it probably belongs only in
`skill-conventions.md` with a project-specific override note in the
host overlay.

## Frontmatter as the portability seam (today)

Even before the directory reorg, `language` and `framework` frontmatter fields
make each skill's encoded assumptions explicit for routing:

```yaml
language: python      # broad encoded assumption: python | any
framework: django     # django | none | any
```

A skill declaring `language: any, framework: any` encodes no broad language or
framework assumption for routing purposes. These fields are not an exhaustive
list of implemented language adapters. Actual host-language eligibility is
recorded separately in
`.claude/tasks/multilanguage-skill-matrix.json` and the named
`<language>-language-coverage.json` files. A skill declaring `language: python,
framework: django` is bound to the host stack and will need adapters when
ported.

`/which-skill` uses these fields to filter recommendations: a TypeScript
project asking for a "split this fat module" skill should not be offered
a Django-bound `/refactor-subsystem` clone.

**Label-flip pass (2026-06-17).** A coupling audit found many skills
carried `framework: django` / `language: python` whose *concept* encodes
no host-stack assumption — the label was host-origin bias, and it was
wrongly *withholding* portable skills from non-Django projects via
`/which-skill`. The seam's rule (per `skill-frontmatter.md`) is that the
fields declare the assumptions the skill *encodes*, not the language its
helper scripts are written in. So:

- Pure-judgment / planning / decision skills that only read ADRs, plans,
  patterns, or reason about scope (`architecture-fit`, `audit-decisions`,
  `plan-spec`, `scope-feature`, `triage-debt`, `teach-pattern`) use the
  `language: any, framework: any` routing declaration. `impact-feature` and
  `plan-feature` are Python/Django stack-bound.
- `prevent-regression` → `language: any, framework: any`; alongside its
  Python paths, it has an accepted TypeScript closed-state guard path.
- `find-omnibus` → `language: any, framework: any` because it processes
  Python, JavaScript, and TypeScript. Its TypeScript Compiler API analysis is
  bundled inside the skill and is self-contained, not implemented through the
  shared language adapter.
- Detectors whose analysis is genuinely Python-AST-bound (the ORM /
  layer / state / FK detectors) **kept** `language: python` even after
  migrating onto the adapter — routing through the seam standardizes
  parsing but does not make their analysis language-neutral. The honest
  label tracks analysis coverage, not plumbing.
- `map-product-workflow` / `extract-workflow-registry` **kept**
  `framework: django` — they parse Django `ROOT_URLCONF` / `urlpatterns`
  directly, which is a real Django assumption.

## The language-adapter seam (landed 2026-06-17)

Roadmap trigger #2 ("a skill needs a clean `_lib/` import path to express
genuine portability") led to the first cross-cutting shared `_lib` module,
`scripts/_lib/lang_adapter/`, which serves a subset of Python and legacy
JavaScript analyzer paths. `find-omnibus` is outside that shared TypeScript
path: its Compiler API launcher is bundled with the skill so copied installs
remain self-contained. See ADR 0032 → *Implementation status* for the shared
adapter's inventory and deliberate non-migration boundary.

This is a partial, opportunistic landing — not the full directory reorg.
One wart it introduces, to be cleaned up when the reorg proper happens:
skill scripts reach `scripts/_lib/lang_adapter` by inserting the repo
`scripts/` dir on `sys.path`, a cross-tree import that the eventual
`_lib/{core,language,framework,repo}` layout will replace with a clean
import path.

## When to revisit the full reorg

Reconsideration triggers, any of which is enough to evaluate the full split:

1. A second host project starts adopting these skills (Django or not).
2. A skill is being written that's genuinely portable and needs a clean
   `_lib/core/` import path to express that.
3. The host-overlay content has grown enough that readers can no longer
   tell which layer a given rule belongs to.

A trigger justifies evaluation rather than automatically committing the full
reorg. Trigger #2 produced the partial shared adapter described above; the full
split remains parked until its additional benefit outweighs the migration cost.
Premature portability splits are themselves a form of speculative abstraction;
the discipline this roadmap enforces is "know where it would go" rather than
"split it now."

## Cross-references

- `skill-conventions.md` — the project-agnostic conventions today (future
  `_lib/core/` payload).
- `skill-frontmatter.md` — the `language` / `framework` field spec.
</content>
</invoke>
