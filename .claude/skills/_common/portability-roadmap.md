# Portability roadmap for `_common/`

The skill ecosystem was originally Django-flavored because that's what
the seed host project needed. The design always anticipated cross-language
adapters (TypeScript, Rust) and cross-framework reuse (Django, FastAPI,
Express). This document pins the planned reorganization so future PRs
don't accidentally cement Django assumptions into shared files.

**Status:** roadmap, not a plan-of-record. The reorg lands when the
first non-Django host project starts adopting these skills, or when a
skill is being written that's genuinely portable and needs a clean
`_lib/core/` import path.

---

## Why this matters

A senior engineer crossing into a new project should not have to re-derive
the skill ecosystem's affordances. The skills are a body of knowledge;
the language and framework are an execution detail. Today, that
distinction is muddled — shared content can mix "every skill follows
this report layout" (project-agnostic) with "use `.venv/bin/python`"
(Python-specific) with host-project-specific test commands.

A new TypeScript host project would need to re-explain the same report
layout to its skills. A new Django-but-different-domain project would
need to re-explain the same Python conventions. That's friction we can
avoid by splitting the shared content along the seams it already has.

## The four-layer split

```
_lib/
├── core/           # Project-agnostic, language-agnostic
├── language/
│   ├── python/     # Python-specific, project/framework-agnostic
│   ├── typescript/ # (future)
│   └── rust/       # (future)
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

Even before the directory reorg, `language` and `framework` frontmatter
fields make per-skill portability explicit:

```yaml
language: python      # python | typescript | rust | any
framework: django     # django | none | any
```

A skill declaring `language: any, framework: any` is portable today and
does not need a port when the reorg lands — it already reads only from
the future `_lib/core/` content. A skill declaring `language: python,
framework: django` is bound to the host stack and will need adapters
when ported.

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
  `impact-feature`, `plan-feature`, `plan-spec`, `scope-feature`,
  `triage-debt`, `teach-pattern`) → `language: any, framework: any`.
- `prevent-regression` → `framework: any` but kept `language: python`
  (its guard-generation path emits Python lint rules).
- `find-omnibus` → `language: any` because it now genuinely processes
  JS/TS through the shared language-adapter seam (see below).
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
genuine portability") effectively fired: the analyzer-adapter pattern of
ADR 0032 was extracted from inside `find-omnibus` into the first
cross-cutting shared `_lib` module, `scripts/_lib/lang_adapter/`, and ~21
AST consumers were migrated onto it. See ADR 0032 → *Implementation
status* for the full inventory and the deliberate non-migration boundary.

This is a partial, opportunistic landing — not the full directory reorg.
One wart it introduces, to be cleaned up when the reorg proper happens:
skill scripts reach `scripts/_lib/lang_adapter` by inserting the repo
`scripts/` dir on `sys.path`, a cross-tree import that the eventual
`_lib/{core,language,framework,repo}` layout will replace with a clean
import path.

## When the reorg actually happens

Trigger conditions, any of which is enough:

1. A second host project starts adopting these skills (Django or not).
2. A skill is being written that's genuinely portable and needs a clean
   `_lib/core/` import path to express that.
3. The host-overlay content has grown enough that readers can no longer
   tell which layer a given rule belongs to.

Until one of those triggers fires, the reorg stays parked. Premature
portability splits are themselves a form of speculative abstraction;
the discipline this roadmap enforces is "know where it would go" rather
than "split it now."

## Cross-references

- `skill-conventions.md` — the project-agnostic conventions today (future
  `_lib/core/` payload).
- `skill-frontmatter.md` — the `language` / `framework` field spec.
</content>
</invoke>
