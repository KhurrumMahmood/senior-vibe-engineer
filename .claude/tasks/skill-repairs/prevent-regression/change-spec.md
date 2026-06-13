# Change spec — /prevent-regression repair (Stage 3)

Inputs: `frame-review.md` (F1–F5, all verified TRUE by `scout.md` with
anchors) + scout corrections (telemetry-append carve-out for F2's
constraint wording). Doctrine: declared verdict, smallest responsible
edits, preserve voice and phase numbering, nothing invented — every
added sentence traces to this spec, scout-quoted text, or pre-existing
SKILL.md text.

## Declared verdict

A fresh, non-context-sharing verifier told to REFUTE will judge each
C-item RESOLVED / PARTIAL / UNRESOLVED by quoting the repaired SKILL.md,
run a no-invention diff audit (old copy frozen at
`/tmp/skill-repairs-old/prevent-regression/SKILL.md`), sweep for new
defects of the same classes (count drift, phantom-artifact references,
staging contradictions), and re-run `.venv/bin/python
scripts/skill_meta.py lint` live. Additionally the repaired text must
keep the Bucket-A output contract scoreable: a guard proposal produced by
following it must place rule + fixtures inside the proposal directory at
repo-relative paths (the shape `scripts/skill_comply/install_proposal.py`
installs from) — checked by the machine-check lane after Stage 5.

## C1 (F1, headline) — add `## How success is judged`

Insert after SKILL.md:48 ("…The human reviews and executes."), before
"Procedural detail lives…". 4–8 bullets instantiating the class-sweeps
gate line ("guard artifact + verification recipe emitted; never
installed unilaterally") plus ONLY gates already mandated elsewhere in
the text: verify_rule BAD_RC=1/GOOD_RC=0 pasted (Phase 3), historical
fire via `git show <anchor>^:<file>` + clean HEAD (Phase 6), bad fixture
covers every variant / good fixture proves quiet on legitimate forms
(Phase 3), test-only branch gates (Phase 3b). No new mandates.

## C2 (F2) — staging contract

(a) A short paragraph adjacent to the C1 block: guard artifacts are
**staged, not installed** — authored under
`reports/prevent-regression/<id>/` at their repo-relative destination
paths; wiring (pre-commit hook, CI step, run.py RuleSpec, CLAUDE.md
bullet) is emitted as ready-to-apply diff blocks in `proposal.md`; Phase
Pre/Post conditions name destination paths and are read against the
staged copies until the human installs. Constraint wording per scout:
"no guard artifact or wiring edit lands in the working tree" (the Phase 6
telemetry append to `reports/_meta/effectiveness.jsonl` stays legal).
(b) Step 7 last bullet: replace "`git add` + commit" with the human
installing the staged artifacts/wiring then committing, or abort if
verification failed.
(c) No phase renumbering; Phases 2–5 bodies untouched except where C4/C5
land.

## C3 (F3) — count fix

SKILL.md:59: "Three forms." → "Four forms."

## C4 (F4) — knowledge/ reality

(a) Rewrite the intro pointer list (SKILL.md:50-55): drop the false
"three knowledge files" framing; point directly at
`_common/skill-conventions.md`; name `knowledge/` as a host-overlay slot
that ships empty in this ecosystem. Keep the `agents/rule-designer.md`
and scripts bullets.
(b) Repository layout tree (SKILL.md:414-416): annotate `knowledge/` as
the empty host-overlay slot; remove the phantom
`(host-overlay specifics).md` file entry.

## C5 (F5) — host-only JS exemplar

SKILL.md:232-235: keep `silent_catch.py` as the Python reference; mark
`no_site_endpoint_sprawl.py` as a source-host rule not shipped in this
ecosystem with an explicit `<!-- host-adapter: ... -->` slot; keep the
portable shape description (suffix expansion, template-literal/
string-concat matching, blockable comments, reason-required `// noqa`)
as the normative content.

## Constraints

- Smallest edits; no renumbering of Phases/Steps; preserve imperative
  voice; nothing invented — gaps become host-adapter slots.
- The harness `proposal_manifest.json` is orchestration glue and MUST NOT
  be added to the skill's output contract (scout §3).
- Implementer does not commit (campaign-wide no-commit constraint).
- After edits: `.venv/bin/python scripts/skill_meta.py lint` must pass.

## OUT OF SCOPE (ledger-routed, not this repair)

- Phase 3 iterate-loop bound (examined, not a finding).
- Emitting `proposal_manifest.json` / formal harness integration of the
  skill output contract — belongs to the skill-comply owner's lane.
- The Class-1 sweep's 40 sibling skills (already specced in
  `class-sweeps-spec.md`; not re-swept here).
- F2's class sweep across the catalog happens at Stage 8, not as edits.
