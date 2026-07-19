# B2P Python closed-state reference proof

Revision: `codex/ts-state-reference`, working tree 2026-07-18 UTC

## Outcome

The Python reference now proves one closed first-party state path end to end:
the detector emits JSONL, collapse produces three stable candidates, checked-in
review buckets the first-party `Job.status` callers for enum extraction and
keeps the vendor wire literal as a reasoned exception, the collector emits
`targets.json`, and the reviewed `JobStatus` before/after mutation makes the
same `stringly-status` guard red then green.

The invariant is: a first-party state carrier has one named symbolic-value
authority; callers neither compare nor assign bare state strings. A vendor
wire literal is allowed only at a named, reasoned boundary.

This is a Python/Django reference proof, not TypeScript support. Tuple identity,
`introduce-fk`, Django migrations, and unrelated `prevent-regression` modes
remain explicitly out of scope.

## Reference repairs

- `find-implicit-state` imported the repository language-adapter registry, so
  an installed selected skill failed before it could emit JSONL. It now uses
  its exact stdlib Python AST requirement directly.
- `extract-enum` imported `_common/scope.py` and `scripts/_lib`, so a copied
  collector failed before resolving a target. Its Python walk and scope-sidecar
  writer now live in the selected skill.
- The collector did not treat a `Job`-annotated function parameter as evidence
  that `job.status` belongs to the selected model. It therefore returned zero
  callers for the reference fixture. Parameter, vararg, and kwarg annotations
  now seed its conservative local-model map.
- The existing `stringly-status` guard caught bare comparisons but silently
  missed `job.status = "queued"`. Its implementation now lives in the
  installed `prevent-regression` state guard and catches field declarations,
  comparisons, and assignments; the root lint is a thin wrapper.

## Fixture and test evidence

`tests/fixtures/b2p_state_reference/` supplies the disposable host:

- `before/` is the first-party Django-shaped `Job.status` smell.
- `after/` is the reviewed `models.TextChoices` mutation.
- `reviewed-scout/` records the two enum-extraction decisions and the reasoned
  vendor boundary.
- `reviewed-profile.md` and `reviewed-proposal.md` are the human-reviewed
  extraction handoff tied to the target literals and callers.

The initial red transcript was captured before repair:

```text
/tmp/es-b2p-red.37PiIP
copied detect.py: ModuleNotFoundError: No module named '_lib'
copied collect.py: ModuleNotFoundError: No module named 'scope'
existing lint: rc=1, 4 hits; the bare assignment was missing

/tmp/es-b2p-collector-red.WKfzqZ
source collector: rc=1, zero comparisons/assignments for Job.status
```

The checked-in B2P test runs the repaired chain and asserts:

- detector: five records (`stringly_field` plus four comparisons), while the
  test fixture and open-ended string filter do not fire;
- collapse: `implicit-state-0001..0003`, with hit counts `1, 3, 1`;
- review report: two `extract_enum_candidate` findings and one
  `legacy_allow_list` vendor boundary;
- collector: `Job.status`, three literals, four comparison records, one
  assignment record, five caller records, and a `scope.json` sidecar;
- guard: before is rc 1 with five lines (including the assignment); after is
  rc 0; direct vendor and open-ended-string checks are clean;
- installed closure: only copied `find-implicit-state`, `extract-enum`, and
  `prevent-regression` directories execute under `python3 -I -S` outside the
  toolkit checkout and without its venv or repository helper directories.

Commands run at one revision:

```bash
.venv/bin/python \
  -m pytest -q tests/test_b2p_state_reference.py \
  tests/test_artifact_scope_adoption.py tests/test_skill_detector_reads.py
# 5 passed

.venv/bin/ruff check \
  .claude/skills/find-implicit-state/scripts/detect.py \
  .claude/skills/find-implicit-state/scripts/collapse.py \
  .claude/skills/find-implicit-state/scripts/report.py \
  .claude/skills/extract-enum/scripts/collect.py \
  .claude/skills/prevent-regression/scripts/stringly_status_guard.py \
  scripts/lint/no_stringly_typed_status.py tests/test_b2p_state_reference.py
# All checks passed

.venv/bin/python \
  scripts/skill_meta.py lint --quiet
# OK — 76 skills, 76 declaring new contract

.venv/bin/python \
  scripts/skill_comply/validate.py
# OVERALL: PASS
```

## B2T contract learned from the reference

Do not start B2T until this evidence is independently accepted. Its minimum
mechanical contract is:

1. Preserve the full outcome boundary, not a parser unit test: stable detector
   JSONL → collapsed/reviewed findings → extraction targets and proposal →
   reviewed before/after mutation → guard red/green.
2. Use a first-party exported runtime value object declared `as const` with a
   derived union type, unless the locked fixture proves a project-native string
   enum convention. Do not copy Django `TextChoices` syntax.
3. Use TypeScript Compiler API program/type facts for receiver attribution.
   The Python reference required parameter annotations to distinguish `Job`
   from `VendorJob`; a lexical TypeScript scan cannot honestly make that
   distinction. Require a project-local compatible `typescript` package and a
   resolvable `tsconfig`, failing clearly when either is absent.
4. Lock positive, enum/value-object clean, vendor-boundary, open-ended-string,
   unrelated-status, test/fixture exclusion, `.ts`, and `.tsx` cases. The guard
   must cover both bare comparison and assignment, and its reasoned `// noqa`
   boundary must stay clean.
5. Keep the Node launcher, detector, collector/proposal support, and state
   guard family-local in selected installed skills. Prove the copied install
   before requesting shared adapters, root dependencies, catalog changes, or
   global lint wiring.
6. Exclude tuple identity/FK, migrations, ORM semantics, and general lint
   generation from TypeScript v1.

## What generalized—and what did not

Generalized: the state-authority invariant, detector/collapse/review/collector
artifact sequence, structured evidence fields, explicit vendor boundary,
before/after guard proof, and copied-install test shape.

Did not generalize: Django `TextChoices`, model discovery by Python AST,
function annotation syntax, `scope.json`'s current Python collector ownership,
and the Python root-lint wrapper. The TypeScript branch must use native syntax
and compiler facts; no parser or shared language adapter is justified by this
single consumer.

## Integrator proposals and residual risk

- Keep B2T's Compiler API launcher and its locked `typescript` resolution
  inside this family until a second accepted consumer needs the same contract.
- After B2T acceptance, the serial integrator may update language-routing
  metadata and decide whether a repository lint wrapper/global runner belongs
  in the product. This B2P change intentionally leaves both untouched.
- The Python guard is lexical for `.status` receivers. Its acceptance boundary
  is the reviewed Django-shaped carrier plus a reasoned vendor exception; it
  is not proof of arbitrary cross-module receiver identity.
- D1, D2, D5, D7, and D8 are evidenced here. D3/D4 are specifically deferred
  to B2T. D6 (fresh non-context installed-skill forward test) is not claimed:
  the parent task forbids spawning that lane while capacity is full and requires
  independent reference acceptance before B2T. Run it after acceptance with
  only the copied skills and raw fixture, not this report or expected result.
