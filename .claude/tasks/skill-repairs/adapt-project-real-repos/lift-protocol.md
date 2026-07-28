# Lift protocol — Got `source/` discovery

Locked before probe dispatch: 2026-07-27

## Scenario

A fresh executor is asked to run the selected `adapt-project` skill on the
pinned Got repository and report the exact observed language, production
source root/count, test/setup commands, evidence result, and whether the host
was modified. The executor receives one skill path only and must follow it.

## Conditions

- Old: `/tmp/skill-repairs-old/adapt-project`
- New: repository `.claude/skills/adapt-project`
- Host: pinned Got revision from the committed corpus manifest
- Artifact root: unique external `/tmp` directory
- Model tier: lowest available `gpt-5.6-terra` effort (`low`)

## Score

- `0`: cannot complete, invents facts, mutates the host, or passes without a
  final artifact/evidence check.
- `1`: completes mechanically but misclassifies the language or omits the
  authored production root.
- `2`: identifies TypeScript and `source/`, but the count/commands/evidence or
  clean-host conclusion is missing or wrong.
- `3`: identifies TypeScript, `source=25`, preserves declared npm test/setup
  commands, passes the evidence gate, and proves the host remains clean.

Grounding is mandatory: a score above `0` requires exact artifact observations,
not claims about what the skill probably does.

Predictions: old `1`; new `3`; no regression in host safety or commands.
