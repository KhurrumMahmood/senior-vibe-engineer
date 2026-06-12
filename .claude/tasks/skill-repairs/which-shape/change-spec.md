# Change spec — /which-shape repair

Inputs: `reports/skill-frame-review/which-shape.md` (F1–F6) + `scout.md`
here (probes reproduced exactly; F5 PARTLY — compact.py consumes
overridden events; new defects). Doctrine: declared verdict,
artifact-truth gates, load-bearing-or-delete, no invention, smallest
responsible edits. This repair touches BOTH prose and `route.py` —
script edits get tests.

## Declared verdict

A fresh verifier re-runs the rubric finding-by-finding AND re-runs the
two live probes plus `route.py --validate`. Pass requires: probe A
(cue-free prompt) no longer presentable as a single confident route per
the new SKILL.md rule; probe B's misroute is either fixed by the new
boost arms or flagged by the override stage; `--validate` fails loudly
on a shape without a boost arm and on cue-constant drift; all tests
green. Write to that test.

## C1 — Low-confidence gate (F1)

SKILL.md rule at the Output section: `confidence: low` or any
"fallback shape candidate" rationale ⇒ do NOT present a single shape;
present the top 2–3 alternatives and ask one discriminating question.

## C2 — Script-is-lexical-prior stage (F2)

Explicit two-line stage after the script run: treat the script output
as a lexical prior, not the decision; if conversation evidence
contradicts the cue match (negation, paraphrase, sarcasm), override
it, say so, and name the cue collision in the reply (so telemetry can
see shadow-routing).

## C3 — Pre-run situation inventory (F3)

Three-line pre-run step: before invoking, check the conversation for
the discriminating dimensions (recurrence? approved proposal in hand?
unknown/inherited repo? scope width? durable choice?) and carry those
words verbatim into the task string — the paraphrase IS the routing
decision.

## C4 — Registry is sole source of truth + scorer coverage (F4)

(a) SKILL.md: delete the enumerated nine-shape list; point at
`shapes.yml` as the sole inventory (fix the frontmatter "such as" list
likewise or mark it illustrative). (b) `route.py`: add boost arms for
`concept-rename` and `task-closeout` (Path B per scout sizing —
30–45 lines; derive cue logic ONLY from those shapes' existing
shapes.yml strong cues, no invented weights beyond parity with
comparable arms). (c) Extend `--validate` to FAIL when any shapes.yml
id lacks a boost arm, and when the in-code cue-constant registry
(route.py:45–54) drifts from shapes.yml strong cues — fix the existing
drift the scout found. (d) Tests for the new arms and both validate
checks. Path A (fully data-driven boosts in shapes.yml) is ledgered as
follow-up, not yours.

## C5 — Telemetry default (F5)

`--outcome` default for `event_kind: recommendation` →
`unscored` (not `useful`). Keep the correction/rerun path documented
(compact.py consumes overridden events) but state its trigger
honestly: it runs when a human notices a misroute, and the metric
counts only scored events. Update any test fixture that assumed
`useful`.

## C6 — Un-fakeable run artifact (F6)

SKILL.md: the script run is mandatory, and the reply must paste the
script's `Project context:` and `Confidence: ... (score=N)` lines
verbatim. Doubles as C1's input.

## C7 — Scout extras (same classes)

Document `--validate` in SKILL.md (one line, where the validate
convention is mentioned). Note in SKILL.md that `narrow` and
context-exemption sets live in route.py (pointer, not relocation —
relocation is part of ledgered Path A).

## Constraints

Smallest edits; preserve voice; script changes covered by tests run
via `python3` (PyYAML available; verify with the repo venv
`.venv/bin/python` if import fails); run the existing route.py test
suite and `--validate` after edits; nothing invented.
