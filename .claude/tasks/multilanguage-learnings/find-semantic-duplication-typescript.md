# TypeScript `find-semantic-duplication` learning packet

Implementation revision: pending lane commit on
`codex/typescript-semantic-duplication`. This packet covers the bounded
function-level TypeScript v1 and the Python reference repairs that were needed
before copying an outcome.

## Accepted v1 contract

The TypeScript branch considers only typed top-level function declarations and
block-bodied arrows with explicit parameter and return types. A confirmed lead
has the same TypeChecker return type and returned object fields, materially
different token sets, no compiler-resolved direct caller→callee relationship,
and compatible throw/try/await policy. It writes final `analysis.json`,
`findings.json`, `triage.md`, and a per-confirmed-finding capability matrix.

The final report separates `confirmed`, `uncertain`, and `rejected`; dynamic
element calls and declaration-only/unresolved direct calls are uncertainty.
Caller→callee, lexical-clone, and divergent-policy pairs are rejected. The
detector does not claim workflow, structural, class/protocol, framework, or
runtime behavior, and never changes source.

The Python reference path now has a bundled stdlib inventory that carries
`end_line` through definitions, summaries, prompts, candidates, and confirms.
The old workflow/artifact inventory outputs were removed from the runnable
function path because no later stage consumed them. `rank.py` and `report.py`
now preserve uncertainty in its own final triage section instead of mixing it
with rejections.

## D1–D8 closeout

| Gate | Evidence | Status |
|---|---|---|
| D1 — scope honesty | Frontmatter declares `language: any`, `framework: any`, `scans: [python, typescript]`; `SKILL.md` names typed top-level functions and all unavailable TypeScript modes. | pass |
| D2 — Python oracle | `tests/test_find_semantic_duplication_python.py` runs a copied selected skill with `-I -S`, proves `end_line` survives collect → prompt → collapse, and proves confirmed/uncertain/rejected separation reaches `triage.md`. | pass |
| D3 — TypeScript final outcome | Locked fixture reaches final `findings.json`, `triage.md`, and matrix: one same-outcome/different-code confirmation, one unresolved/dynamic uncertainty, and caller/lexical/policy rejections. | pass |
| D4 — change/guard | Not applicable: this is a read-only SUSPECT detector. | n/a |
| D5 — installed closure | Test uses the exact stock `skills@1.5.19 add … --skill find-semantic-duplication --copy` command, runs the installed documented command, and resolves only host-local TypeScript. | pass |
| D6 — fresh forward task | Automated selected-install final-artifact replay passes; independent non-context agent replay remains for the serial integrator. | pending integrator replay |
| D7 — regression/conformance | Focused Python/TypeScript suite, Ruff, Node syntax check, metadata lint, native offline typecheck before/after scan, and diff check pass. Direct exclusions, symlinks, output containment, missing compiler/config, syntax error, and source immutability are covered. | pass |
| D8 — learning handoff | This Markdown and JSON packet record the reference repair, family-local resolver decision, evidence, false-positive boundary, and deferred D6. | pass |

## Verification

```text
.venv/bin/python -m pytest \
  tests/test_find_semantic_duplication_python.py \
  tests/test_find_semantic_duplication_typescript.py -q
# 5 passed

.venv/bin/ruff check \
  .claude/skills/find-semantic-duplication \
  tests/test_find_semantic_duplication_python.py \
  tests/test_find_semantic_duplication_typescript.py
# All checks passed

node --check .claude/skills/find-semantic-duplication/scripts/detect_typescript.mjs
# passed

.venv/bin/python scripts/skill_meta.py lint
# OK — 76 skills, 76 declaring new contract
```

The direct native replay at `/private/tmp/semantic-duplication-native.dIRql7`
ran `npm ci --offline --ignore-scripts`, `npm run typecheck`, the final skill
command, then `npm run typecheck` again. It produced exactly `TS-SD-0001`, one
uncertainty, three rejections, and the capability matrix without source edits.

## Tool and reuse decision

`detect_typescript.mjs` uses a project-local TypeScript 5.9.3 Compiler API,
named `tsconfig`, `Program`, and `TypeChecker`. It copies the accepted
map-subsystem containment and host-compiler resolution pattern locally, but
does not import its map schema or create a shared resolver. This detector needs
symbol identity for direct-call exclusions and type facts for the typed-output
contract; a lexical parser or jscpd cannot establish those boundaries.

Keep it family-local. The only demonstrated shared material is the operational
pattern (host-local compiler, named config, project-relative exclusions,
symlink-safe reports, selected-skill closure), not a common interface. A
future consumer must independently prove the same input/output/closure shape
before an abstraction is considered.

## Residual risks and next decision

This v1 deliberately misses semantic duplicates with different output shapes,
expression-bodied arrows, nested functions, class/protocol methods, dynamic
dispatch, runtime effects, and framework conventions. Matching static output
shape remains an advisory lead rather than refactor authority. The host must
provide Node, a project-local TypeScript package, and a valid named tsconfig.

Next: the serial integrator can perform the D6 clean-host/no-context forward
replay, then accept the report schema before beginning `unify-shadows`. Do not
expand to workflow/structural analysis, shared TypeScript infrastructure, or
UX/performance work in this lane.
