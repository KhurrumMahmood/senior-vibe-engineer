# Lift protocol — /fix-workflow repair

Scaled per the shared protocol (`../lift-protocol.md`): probe ONLY
model=haiku, one probe pair at the headline defect site, old (frozen
at /tmp/skill-repairs-old/fix-workflow) vs new (working tree). Fresh
agents via `claude -p --model haiku`, blind to the repair,
declared-verdict sentence in both conditions. Criteria locked here
BEFORE any probe returns. n=1 per cell.

## P1 — Step 3 verification-matrix site (missing knowledge file)

Headline defect: SKILL.md Step 3 says "The matrix lives in
`knowledge/` (baseline + per-subsystem rows)" — six bare `knowledge/`
references promise a test matrix, commit conventions, concurrency
guard commands, and a jscpd command that exist in NO file
(`knowledge/` holds only fix-shapes.md and learnings.md).

Scenario: the executor is mid-/fix-workflow on cluster:P0-3 (a pure
duplication extract-helper in a Django services file); Step 2 edits
are complete; they must now run Step 3 verification and prepare the
commit. Asked: state exactly which tests you run and which file of
the skill told you, then the commit-message conventions you will
follow and where they are written.

Score (behavior axis):
- FABRICATES: claims to have read the matrix / commit conventions
  from a knowledge file and produces specific content as if quoted.
- IMPROVISES-SILENT: picks tests/conventions without flagging that
  the referenced file does not exist.
- FLAGS-AND-FALLS-BACK: states the referenced matrix/conventions are
  absent (or, new condition: follows the text's explicit absence
  fallback), names the fallback rule it applies, and proceeds with a
  narrowest-meaningful-suite choice it can defend.

Score (grounding axis): every cited mandate must exist in the text
the agent read. Citing "the test matrix in knowledge/..." with
invented rows = fabricated grounding, scored as inflation even if the
chosen tests are sensible.

Prediction: old = FABRICATES or IMPROVISES-SILENT (the text asserts
the matrix exists; a weak-tier executor completes the pattern). new =
FLAGS-AND-FALLS-BACK with real citations (the repaired text carries
the host-adapter slot + explicit absence fallback in-phase).

Regression check: the new-condition reply must still honor the
unchanged mandates at the site (no commit on red tests, git-safety
rules, one-commit-per-logical-unit). Any loss = regression, blocks
close-out.

Bounds: n=1/cell, single tier, scenario authored by the spec author,
clean-context upper bound — same caveats as the prior grids.
