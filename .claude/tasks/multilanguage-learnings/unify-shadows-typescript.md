# TypeScript `unify-shadows` learning packet

Implementation revision: `d2b33542f9f1afa695fa0385251e73ba8df91515`
on `codex/typescript-unify-shadows`.

## Accepted TypeScript v1 contract

`unify-shadows` now consumes exactly one confirmed function-level TypeScript
record from the accepted `/find-semantic-duplication` `findings.json`. It
validates skill kind, language, confirmation status, level, shape, current
`.ts`/`.tsx` source spans, and capability-matrix evidence before it creates an
output directory. Missing, unconfirmed, rejected, uncertain, malformed, or
wrong-kind input exits 2 before synthesis.

The final read-only handoff is
`reports/unify-shadows/<finding-id>/{proposal.md,evidence.json,scope.json}`.
Every proposal cites member spans and capability-matrix rows, identifies source
impact, renders caller limitations honestly, names host-native typecheck/test
commands, states shape-specific stop conditions, requires human approval, and
hands off without changing host source.

All four shapes have an explicit honest outcome. `keep_separate_document_why`
preserves both implementations and emits no consolidation or caller-move plan.
`share_utilities` names a candidate seam but gates it on characterization and
the deletion test. `complete_migration` treats the first member only as a
provisional survivor until human review supplies ownership evidence.
`merge_at_workflow` blocks implementation until a human supplies the workflow
authority because upstream TypeScript v1 explicitly marks workflow analysis
unavailable.

## Tool, closure, and reference-repair decision

The new `scripts/propose_typescript.mjs` is a family-local JSON/filesystem
consumer, not another TypeScript analyzer. Node is already required by the
upstream TypeScript scan; no compiler API, shared resolver, repository script,
toolkit venv, sibling skill, or network runtime is needed after the selected
skill is copied. A second shared infrastructure layer would add an interface
without a second compatible consumer.

Two upstream-independent Python defects were repaired locally:

- `collect_shadows.py` now accepts legacy `? callers` and preserves it as
  `caller_count: null` instead of dropping the member.
- A copied selected skill now writes the version-1 `scope.json` sidecar with a
  bundled stdlib fallback when repository `scripts/_lib/artifact_scope.py` is
  absent.

The TypeScript consumer also corrects the interpretation boundary: upstream
`caller_count` counts compiler-resolved incoming calls from the eligible
candidate graph, not complete host caller locations. Zero is rendered as zero
in that graph plus a mandatory full-project reference inventory; null/-1 is
rendered unknown. Neither becomes “no callers.”

## Locked fixture and acceptance evidence

`tests/fixtures/unify-shadows-typescript/host` freezes the accepted
`TS-SD-0001` finding and matrix derived from the confirmed
`summarizeByReduction` / `summarizeByLoop` pair. Its native test asserts both
implementations return the same observable result; TypeScript 5.9.3 is pinned
in the lockfile.

`tests/test_unify_shadows_typescript.py` covers:

- positive final proposal/evidence/scope output with source and matrix
  citations;
- all four shape templates, including the keep-separate must-not-fire check;
- missing, unconfirmed, wrong-skill, wrong-language, wrong-level, and
  not-confirmed-status pre-synthesis failures;
- output escape and symlink rejection, source hashes before/after, and native
  typecheck/test before/after;
- the exact `skills@1.5.19` selected-skill copy plus the exact documented
  installed command; and
- legacy unknown-caller parsing plus scope fallback from a copied skill with no
  repository helper.

## D1–D8 closeout

| Gate | Evidence | Status |
|---|---|---|
| D1 — scope honesty | Frontmatter is `language: any`, `framework: any`, `scans: [python, typescript]`; TypeScript v1 names its structured function-only boundary and unavailable workflow/runtime/caller facts. | pass |
| D2 — reference oracle | Existing Markdown/Python behavior remains; focused tests prove unknown callers survive and the selected-copy scope sidecar no longer disappears. | pass |
| D3 — TypeScript final outcome | Locked confirmed finding reaches evidence-cited proposal/evidence/scope artifacts for all four shapes; invalid inputs fail before synthesis. | pass |
| D4 — change/guard | Not applicable: this EXPLAIN skill is read-only. Proposal stop conditions require characterization plus native verification before downstream edits. | n/a |
| D5 — installed closure | Exact stock selected-skill copy and exact installed proposal command pass without repository runtime dependencies; host source hashes remain unchanged. | pass |
| D6 — fresh forward task | A fresh no-context installed replay produced the `share_utilities` proposal with cited source/capability evidence, caller limits, native tests, stop condition, approval gate, invalid-input abstention, and unchanged source. | pass |
| D7 — regression/conformance | Focused pytest, native TypeScript checks, Node syntax check, Ruff, metadata lint, and diff checks pass. | pass |
| D8 — learning handoff | This Markdown and companion JSON preserve contract, evidence, reuse decision, risks, and the blind forward task. | pass |

## Verification

```text
.venv/bin/python -m pytest \
  tests/test_unify_shadows_typescript.py \
  tests/test_artifact_scope_adoption.py -q
# 15 passed

npm ci --offline --ignore-scripts \
  --prefix tests/fixtures/unify-shadows-typescript/host
npm run typecheck --prefix tests/fixtures/unify-shadows-typescript/host
npm test --prefix tests/fixtures/unify-shadows-typescript/host
# passed

node --check .claude/skills/unify-shadows/scripts/propose_typescript.mjs
.venv/bin/python -m ruff check \
  .claude/skills/unify-shadows/scripts/collect_shadows.py \
  tests/test_unify_shadows_typescript.py
.venv/bin/python \
  scripts/skill_meta.py lint
git diff --check
# passed
```

## Fresh-forward packet and remaining boundary

Give a fresh non-context agent only a clean copy of the locked host, the
installed `unify-shadows` skill, and this natural task:

> Review the confirmed TypeScript semantic-duplication finding
> `TS-SD-0001`. Produce the proposal artifact, explain what source and caller
> work would be required, state the native verification and stop condition,
> and do not edit application source.

The integrator ran this blind replay without disclosing expected shape, member
names, or negative assertions; it passed the artifact, command, native-check,
source-hash, and approval gates.

Residual risks are deliberate: the static upstream finding cannot prove
runtime equivalence, framework dispatch, external consumers, a canonical
survivor, a deep utility seam, or workflow authority. This consumer exposes
those gaps instead of filling them with invented plans. Keep tooling
skill-local; UX improvements remain later work.
