# Frame review — prevent-regression (Stage 1, inline)

> **Limitation.** Run INLINE by the campaign orchestrator (spend
> constraint), not by a fresh sub-agent. The reviewer shares context with
> the intake evidence (class-sweeps-spec, Bucket-A doc) and so is primed
> toward the class-1 defect; treat negative findings ("nothing else
> wrong") with less confidence than positive ones. Rubric:
> `.claude/skills/repair-skill/knowledge/frame-review-rubric.md`, all six
> lenses applied to SKILL.md + `agents/rule-designer.md` + script
> contracts derived live via `--help` (verify_rule.py, generate_rule.py).

## What the skill gets right

- **Real artifact-truth gates exist.** Phase 3's `verify_rule.py`
  (BAD_RC=1 / GOOD_RC=0) is a genuine differential verifier, invoked by
  exact command. Phase 6's verification template demands historical-fire
  (`git show <anchor>^:<file>`) and clean-on-HEAD with pasted results —
  these are the C3/C4 analogues the conformance harness later formalized.
  This is far better than file-existence theater.
- Phase Pre/Post conditions per phase; fixture-pair doctrine ("every
  variant" in bad, legitimate forms in good) covers both precision and
  recall at the fixture level; non-goals bound scope well.
- Hallucination-resistance is good: verification asks for RCs, hit
  counts, and file lists, not assertions.

## Findings

### F1 (headline, class-1) — no declared-verdict block [GOAL]

The skill never states, up front, how a run is judged. The gates exist
but are diffused across Phase 3 and the Phase 6 template; an executor
that produces a plausible `proposal.md` can treat file completion as
done without internalizing that the run is graded by (a) emitted-not-
installed, (b) its own verifier passing, (c) historical fire, (d) no
stray firing. Class-sweeps-spec names this skill a confirmed Class-1 hit
(citation SKILL.md:191). Bucket-A status raises the stakes: the output
contract is machine-scored (C1–C9), so the verdict block should name the
side-effect gates the scorer re-runs.
**Smallest fix:** add a 4–8-line `## How success is judged` block after
the intro, instantiating the spec-gate line ("guard artifact +
verification recipe emitted; never installed unilaterally") plus the
existing Phase 3/6 gates. No new mandates — summarize gates already in
the text.

### F2 (moderate) — write-site contradiction: proposal-only vs in-tree posts [FRAME]

The frame ("produces a **proposal** under `reports/prevent-regression/
<id>/` and **stops**. The human reviews and executes" — intro; "Read-only
against production code — never installs the guard unilaterally" —
description) is established in the preamble and never re-activated at the
write sites. The Phase Post conditions then read as in-tree mandates:

- Phase 2 Post: "`scripts/lint/<rule>.py` exists and is smoke-tested."
- Phase 3 Post: "`tests/lint/<rule>_bad.<ext>` + `<rule>_good.<ext>` exist".
- Phase 4 Post: "`.pre-commit-config.yaml` **has** a `local` hook entry…
  `.github/workflows/ci.yml` **has** a diff-scoped step".
- Phase 5 Post: "`.claude/CLAUDE.md` **has** a new bullet".
- Step 7: "Next recommended action: `git add` + commit".

An executor who follows the Posts literally wires the hook and edits
CLAUDE.md in the working tree — at which point the guard IS installed
(pre-commit hooks act on the next commit) and only the commit is left to
the human, contradicting "produces a proposal and stops". An executor who
follows the intro instead has no stated staging location for the rule
script/fixtures and must improvise. This is the exact ambiguity the
harness resolves the other way: `install_proposal.py` expects guard
artifacts INSIDE the proposal directory at repo-relative paths and is
itself the install step. Execution failure produced: divergent runs
(in-tree vs staged), and the Bucket-A grading path breaks when artifacts
are not in the proposal dir.
**Smallest fix:** one staging-contract paragraph after the intro stating
that guard artifacts are staged under the proposal dir mirroring their
repo-relative destinations, wiring is emitted as ready-to-apply diff
blocks in `proposal.md`, and Phase Posts are read against the staged
paths; align Step 7's "git add + commit" line to "human installs then
commits".

### F3 (minor, drift) — "Three forms" routes four [WORKFLOW TRAPS]

"## Argument parsing — Three forms. Detect and route:" precedes Forms
A, B, C **and D** (`topology:<template>`). Count drift; trivially
confuses a literal executor.
**Smallest fix:** "Four forms."

### F4 (minor, artifact-reality drift) — empty `knowledge/` claimed as content

Intro: "Procedural detail lives in three knowledge files: `knowledge/` —
shared conventions (points at `_common/skill-conventions.md`) plus
custom-lint patterns we've adopted…" and the Repository layout lists
`knowledge/(host-overlay specifics).md  # pointer to _common + skill-local
rules`. Reality: `.claude/skills/prevent-regression/knowledge/` is empty
(verified by ls). An executor sent there for conventions finds nothing
and must improvise the pointer to `_common/skill-conventions.md`.
**Smallest fix:** reference `_common/skill-conventions.md` directly and
mark `knowledge/` as an empty host-overlay slot in both places.

### F5 (minor, artifact-reality drift) — `no_site_endpoint_sprawl.py` does not exist here

Phase 2: "For JS lexical guards, mirror the `no_site_endpoint_sprawl.py`
shape…". No such file exists in this repo (`scripts/lint/` verified); it
is a host-a rule that was never ported. An executor told to mirror it
cannot read it.
**Smallest fix:** mark it as a host-a exemplar not shipped here with a
host-adapter slot, keeping the listed shape properties (suffix expansion,
template-literal matching, reason-required `// noqa`) as the portable
content.

## Examined, not findings

- Phase 3 "If either is wrong, iterate on the rule or fixtures" has no
  iteration bound — but the loop is gated by a deterministic verifier and
  ends at a human review; not flagged.
- `tests/lint/` absent in this repo: those are host-project destination
  paths for the proposal, not references the executor must read — correct
  as written once F2's staging contract exists.
- Load-bearing audit: `pattern.md` is consumed by Phases 2–3 (AST shape)
  and `proposal.md`; `effectiveness.jsonl` append uses the shared
  `scripts/log_effectiveness.py` (exists). No ceremony stages found —
  consistent with the Class-2 sweep, which examined prevent-regression
  and did not list it.
- Dispatch/write tool check: `allowed-tools: Bash, Read, Grep, Glob,
  Write, Edit, Agent` covers the rule-designer scout dispatch and all
  writes. Consistent with the Class-3 sweep (not a hit).
