# Repository topology plan — delivery operations host

Status: plan-only. No moves were applied and no references were rewritten.

## Folder value inventory

| Current path | Lifecycle | Reader question and value |
| --- | --- | --- |
| `README.md`, package files, `tsconfig.json` | root-signpost | What is runnable and how is TypeScript discovered? |
| `src/` | runtime | Where do webhook intake, metric ownership, and retry calculation execute? |
| `tests/` | tooling/proof-machinery | What native host behavior is guarded? |
| `scripts/lint/` | tooling | Which host-specific contract guard runs in `npm test`? |
| `docs/decisions/` | build-commitment | Which choices constrain future delivery work? |
| `docs/known-issues.md` | doctrine-kb | Which current operational gaps must remain visible? |
| `kb/` | doctrine-kb | Where do short source maps and operational explanations live? |
| `inputs-1/` | raw-source-material | Where are immutable first-pilot payload snapshots? |
| `outputs/` | proof-machinery | Where is the latest derived reconciliation run record? |
| `reports/` | proof-machinery | Where do agent and phase reports accumulate? |

## Abstraction ladder

First pass: runtime and native tooling are already cohesive; decisions and
known issues record commitments and current truth; imported inputs and derived
outputs are separated only by historical root names.

Second pass: the repeated boundary is lifecycle, not language. Raw source
material is consumed by proof work, while reports and run records are derived;
neither belongs in the knowledge base or runtime.

Third pass: the smallest stable navigation keys are `src`, `tests`, `scripts`,
`docs`, `kb`, `source-materials`, `evals`, and `reports`. The root package and
TypeScript configuration remain signposts because the toolchain discovers them
there.

## Ideal topology

```text
.
├── README.md
├── package.json / package-lock.json / tsconfig.json
├── src/
├── tests/
├── scripts/lint/
├── docs/
│   ├── decisions/
│   └── known-issues.md
├── kb/
├── source-materials/
│   └── webhook-fixtures/
├── evals/
│   └── run-records/
└── reports/
```

## Constrained target topology

The constrained target equals the ideal logical topology except that the
package files, `tsconfig.json`, `src/`, `tests/`, and `scripts/` remain at their
current discovery locations. Moving those would add toolchain cost without a
navigation gain. `inputs-1/` becomes `source-materials/webhook-fixtures/` and
`outputs/` becomes `evals/run-records/`; imported snapshots remain intact.

## Naming-context decisions

| Old name | New name | Context | Default action | Evidence or constraint |
| --- | --- | --- | --- | --- |
| `inputs-1` | `source-materials/webhook-fixtures` | operational name with provenance-bearing contents | rename under clearer owner | chronology does not answer the reader question; preserve snapshot contents intact |
| `outputs` | `evals/run-records` | operational | rename | active derived records need a purpose label, not a generic result bucket |
| `src` | `src` | compatibility | keep | `tsconfig.json` and package commands already discover this runtime root |
| `kb` | `kb` | compatibility/human preference | keep provisionally | its README states a distinct knowledge purpose; rename only with human preference |

## Deterministic moves

One reviewed `/move-path` batch can move `inputs-1/` to
`source-materials/webhook-fixtures/` and `outputs/` to
`evals/run-records/`, then update exact path references in Markdown, JSON, and
YAML. A dry run must classify `outputs/latest.json`'s `inputs-1` value as an
operational reference rather than silently treating it as historical prose.

## Judgment and manual follow-up

- Decide whether `kb` is the team's durable word or should become
  `docs/knowledge`; do not combine that preference decision with the safe
  source/output demotion.
- Add README signposts to `source-materials/`, `evals/`, and their owned
  children in the same applied change.
- Review prose uses of first-pilot labels as provenance before rewriting.
- Keep `reports/` separate from committed eval run records until retention and
  ownership are decided.

## Validation and stop condition

Before any apply: review the move map, suggestions, blocked findings, and Git
impact. After an authorized apply: run `/move-path --check`, `npm run
typecheck`, `npm test`, a JSON parse of moved manifests, `git diff --check`,
and an operational residue search for both old paths. Stop when those checks
pass and only intentionally historical references remain.

## Installed-closure disclosure

The exact selected-skill copy contains this `SKILL.md` but not sibling doctrine
`_common/structural-design-principles.md` or the separate `/move-path` skill.
This plan applies the structural tests embedded in the selected skill and does
not claim the missing doctrine was read, a move plan was generated, or a dry
run occurred. Stock structural redesign therefore retains a doctrine and
mechanical-handoff UX gap even though the language-independent plan outcome is
reviewable.
