# Learnings distilled from prior cleanup clusters (R1-R14)

This file is loaded by the orchestrator **when stuck on a judgment
call** — not front-to-back on every run. The inline checklist in
`SKILL.md` handles the happy path; this file covers edge cases where
the shape isn't obvious.

Rules are provenance-anchored to the cluster that surfaced them. Each
has a "How to apply" line so you can match it against the current
cluster quickly.

## R1 — Behavior preservation ≠ correctness

A correct refactor of broken code is still a correct refactor. Keep
refactor and fix in **separate commits** so `git bisect` and code
review work cleanly.

**How to apply:** If you spot a latent bug while lifting a helper,
commit the refactor first with "Behavior preserved, including <bug>",
then commit the fix as a follow-up.

## R2 — Write a test before trusting the fixture

If the refactor target has no test coverage, a sub-agent writing a
test fixture will surface bugs that "running the existing tests"
misses. Cluster 1b's `AttributeError` was found this way, not by
running the refactored code.

**How to apply:** For any low-coverage target, write a fixture-level
test **before** you start the refactor. Run it first to confirm it
passes against the pre-refactor code.

## R3 — Log format is behavior

Never unify log strings as part of a refactor. Downstream aggregators
and humans depend on exact format. Drift cleanup is its own commit.

**How to apply:** When extracting a helper, leave each caller's log
lines in place at the caller. If the log lines drift across clones,
note it as a follow-on finding; don't "clean it up" during the
refactor.

## R4 — Keyword-only policy flags

When a helper takes a policy flag (e.g., `reclassify: bool`), make it
keyword-only (`*, reclassify: bool`). Call sites read naturally and
accidental positional-arg bugs are impossible.

**How to apply:** Any helper signature with a bool-or-enum-shaped
parameter should have `*,` before it. Never accept policy flags
positionally.

## R5 — Universal-None adapter for mixed control flow

Helpers called from both loop contexts (`continue`) and single-shot
contexts (`return None`) should return `None` on failure, not raise.
Let each caller pick its own control flow.

**How to apply:** When a helper is called from `for` loops and from
one-shot paths, return `None` on failure. Callers decide between
`continue`, `return None`, or `raise` at the call site.

## R6 — Helper location defaults to module scope

Class membership only if the class has stateful methods the helper
belongs with. No `HydrationDetector._find_script_and_parse_json`
boilerplate when a module-level `_find_script_and_parse_json` does
the job.

**How to apply:** Default to module scope. Put the helper inside a
class only if it reads `self.<something>` or needs method resolution
order.

## R7 — Three outcomes for shadow-helper findings, not one

True shadow → delete. Canonical gap → promote new helper to canonical.
Module-local concept → skip. Read **both** bodies before choosing.

**How to apply:** Before touching a shadow, diff the shadow body
against the canonical body. If semantics match: delete the shadow.
If canonical can't do what shadow does: promote a new canonical
helper (2-commit cluster). If the shadow is tightly coupled to a
module-private concept: skip the cluster entirely.

## R8 — Partial-failure reorderings need documentation

When a refactor reorders side effects on independent tables (Cluster
5), the happy path is unchanged but the crash-recovery behavior
shifts. Document the choice in the commit message.

**How to apply:** If the refactor changes the order in which you
write to multiple databases/tables/files, call it out explicitly in
the commit message: "Side effects now run in order A→B (was B→A); on
crash between them, A is committed and B is not, which is
<acceptable / matches the dominant caller / etc>."

## R9 — Ranking heuristic: narrow divergence → easier lift

When the divergence surface is at the edges (input gathering, output
shaping), the helper owns the middle. When the divergence is threaded
through the body, consider keeping it as two functions and accepting
the duplication.

**How to apply:** Before extracting, ask: "Is the divergence at the
top/bottom, or woven through?" Top/bottom divergence = clean helper.
Woven divergence = don't force a helper, two similar functions are
fine.

## R10 — Keep test scope tight but matching

Don't run the full repo test suite for a single-file refactor. Use
the test matrix in `knowledge/verification.md` — it maps cluster subsystems
to test modules and is fast under the SQLite test settings.

**How to apply:** Look up the touched file in the test matrix. If
the file isn't listed, run the nearest subsystem suite plus the
baseline. Only run "all tests" when the refactor is intentionally
cross-cutting.

## R11 — Never delete unilaterally during a fix

If a fix-mode workflow surfaces unrelated dead code, report it as a
follow-on finding. Deletion is a strictly larger blast radius than
fixing; it gets its own authorization cycle.

**How to apply:** When executing `/fix-workflow fix:<name>`, do not
delete adjacent dead code in the same commit. Log it under
"Follow-on findings" in the learnings entry. The user launches a
separate `/fix-workflow delete:` for each.

## R12 — Two-helper extraction beats one mega-helper

If a cluster has four affected methods with two clearly-distinct
patterns (like Cluster 6's Start/Reclassify vs. the progress
endpoints), extract two focused helpers rather than forcing a common
abstraction with a mode parameter.

**How to apply:** If you find yourself threading a `mode` parameter
into a helper to cover two patterns, split into two helpers. The
"shared middle" is probably only superficially shared.

## R13 — Trust the existing test suite for well-covered areas

If `tests_custom_site` has 32 tests and your refactor passes all of
them, you don't need to add tests for the refactor itself — they'd
be redundant. Add tests only where coverage is missing (typically
the Cluster 1b / sub-agent-discovered-bug scenario).

**How to apply:** Check the test module's assert count. If it's
>=10 and all pass, skip adding refactor-proof tests. If it's <5, add
a fixture-level test that exercises the helper's main path.

## R14 — Re-scan after the fix

The post-cluster jscpd re-scan in Step 3 is the only way to confirm
the clone actually dropped. Without it, you're trusting your own
change to have done what you claimed.

**How to apply:** After committing, run jscpd on the touched subdir
and diff the clone count against `reports/duplication/latest/jscpd/`.
Fewer clones = success. Same-or-more clones = the refactor didn't
land; investigate.
