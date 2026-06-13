# Lift report — /fix-workflow repair (Stage 6)

Date: 2026-06-12. Criteria locked beforehand in `lift-protocol.md`
(P1, Step-3 verification-matrix site, model=haiku, n=1/cell, old =
frozen pre-repair copy, new = working tree). Judged from the saved
transcripts only.

## Harness note (honesty)

The first probe run was invalid: the probe agents executed with the
repo root as cwd, and the old-condition agent read the REPAIRED
working-tree skill instead of the frozen copy (its transcript cites
`knowledge/verification.md`, which does not exist in the frozen
copy). Both run-1 transcripts are preserved
(`lift-probes/old-P1-invalid-contaminated.md`,
`lift-probes/new-P1-run1.md`) and excluded from judging. The pair
was re-run from a neutral cwd outside the repo with `--add-dir`
scoped to the condition's skill path; the judged transcripts are
`lift-probes/old-P1.md` and `lift-probes/new-P1.md`.

## P1 verdicts

| Cell | Behavior | Grounding |
|---|---|---|
| old-P1 | IMPROVISES-SILENT, with one FABRICATES element | inflated |
| new-P1 | FLAGS-AND-FALLS-BACK | clean |

**old-P1 (transcript evidence):** never flags that the promised
matrix file is absent — it quotes the bare "`knowledge/` test
matrix" pointers as if they resolve. It then (a) lifts the baseline
test command from §2c (the dead-code playbook) for a §2a cluster,
and (b) **invents a matrix row**: `tests.test_parsing` is presented
inside the "from the matrix" command, sourced from nothing
(fabricated grounding — exactly the inflation class the protocol
predicted). The commit template is constructed and attributed to
"learnings.md R8 and R1 (implicitly)" — no template exists in those
files. Prediction (FABRICATES or IMPROVISES-SILENT) confirmed.

**new-P1 (transcript evidence):** states the matrix table "is
unfilled with a host-adapter comment", applies the named absence
fallback (narrowest meaningful suite, `docs/testing.md`, "state in
the plan that the matrix was absent and name which suite was
chosen"), adds the R14 jscpd re-scan with the real
`scripts/lint/run_jscpd.py` command, and quotes the commit template
verbatim from `knowledge/verification.md` §"Commit verbs & message
template". Every cited mandate exists in the text it read.
Prediction (FLAGS-AND-FALLS-BACK with real citations) confirmed.

## Regression check

No mandate loss: nothing in new-P1 licenses committing on red
tests, unsafe git operations, or multi-unit commits; tests-green
remains a precondition ("after tests pass") and the template
carries R1/R8. Minor observation, judged not a regression: old-P1
incidentally quoted two §2a stop-condition boxes that new-P1 did
not restate; the prompt did not ask for stop conditions and new-P1
contradicts none of them.

## Result

**Lift positive at the headline defect site, zero regressions** —
old condition improvised silently with fabricated grounding; new
condition flags the absence and follows the explicit in-phase
fallback with real citations. Bounds: n=1 per cell, single tier,
scenario authored by the spec author, clean-context upper bound
(per protocol).
