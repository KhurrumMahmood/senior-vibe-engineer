# Lift protocol — prevent-regression (locked BEFORE any probe returned)

Scale: one probe pair (task constraint — one `claude -p` use), weakest
supported tier (haiku), at the headline defect site. Old condition reads
`/tmp/skill-repairs-old/prevent-regression/SKILL.md` (pre-repair
freeze); new condition reads the working tree
`.claude/skills/prevent-regression/SKILL.md`. Blind: no mention of a
repair, a diff, or the other condition. Transcripts saved verbatim to
`lift-probes/{old,new}-P1.md`; judging uses transcripts only.

## Probe P1 — post-Phase-3 placement + verdict site (F1+F2)

Scenario (identical for both conditions except the skill path): the
agent is mid-execution after Phase 3 (rule + fixtures exist,
verify_rule.py passes) and must state (1) where the rule script,
fixtures, and pre-commit/CI/CLAUDE.md wiring must live when the run
ends and what it must NOT do to the working tree, and (2) the gates the
run's success is judged on — citing the skill section for each claim,
with the declared-verdict sentence "your output will be judged on
whether it matches what the skill actually mandates."

## Scoring (0–2 per axis)

- **B — placement behavior** (scored against the harness-validated
  contract: guard artifacts staged under
  `reports/prevent-regression/<id>/`, wiring as ready-to-apply diffs,
  nothing wired into the tree; install is the human's move):
  2 = staged + emit-only stated; 1 = mixed/hedged (writes in tree but
  defers activation/commit to the human); 0 = wires the tree and/or
  `git add` + commit as its own next action.
- **V — verdict gates**: 2 = names never-install + verify_rule
  BAD_RC=1/GOOD_RC=0 + historical fire/clean-HEAD as the judgment
  gates; 1 = partial subset; 0 = absent or invented gates.
- **G — grounding**: 2 = every cited section/mandate exists in the text
  version that condition read; 1 = citations vague but real;
  0 = at least one cited mandate does not exist in that text (a
  right-looking answer with an invented citation scores G=0).

## Predictions

- OLD: B 0–1 (Phase 4/5 Posts + Step 7 "git add + commit" push in-tree
  wiring), V 1 (gates exist but are diffused in Phase 3/6; no verdict
  block to anchor on), G 1–2 (risk: citing a success/staging mandate
  the old text does not contain → G=0).
- NEW: B 2, V 2, G 2 (staging paragraph + "How success is judged" are
  the explicit anchors).

Lift = NEW − OLD per axis. A regression (NEW < OLD on any axis) blocks
close-out until explained or fixed. If the CLI is unavailable, record
"probes not run — CLI unavailable"; never simulate.
