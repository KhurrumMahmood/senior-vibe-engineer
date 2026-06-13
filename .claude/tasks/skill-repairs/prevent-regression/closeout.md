# Close-out — prevent-regression repair (Stage 8)

## Class-lift gate (NEW classes only; Class 1 already swept catalog-wide)

**Class A — emit-only contract contradicted by in-tree "git add" next
action (F2's class).** Detector (run 2026-06-12):
`grep -l "git add" .claude/skills/*/SKILL.md` intersected with
`grep -qiE "read-only|never install|proposal.*stops|emits a proposal"`.
**Hits: 0** (the repaired prevent-regression no longer matches). No
siblings to batch.

**Class B — SKILL.md cites skill-local `knowledge/` content while the
dir ships empty or missing (F4's class).** Detector: per-skill loop —
`grep 'knowledge/' SKILL.md` AND (`knowledge/` missing or `ls -A` empty).
**Raw hits: 5.** Triage: prevent-regression (post-repair honest mention —
FP), which-skill (explicitly says "No `knowledge/` directory" — FP),
**3 confirmed siblings**: extract-enum, introduce-fk, unify-shadows (all
tell scouts to read `knowledge/` files that do not exist). Batched as one
sweep candidate, ledgered on `repair-skill` (note event, 2026-06-12) —
same one-edit shape as this campaign's C4. Not mechanizable cheaply
beyond the loop above; `find-skill-artifact-drift` Band B is the standing
detector home if promoted.

**Class C — SKILL.md references a `scripts/lint/*.py` absent from disk
(F5's class).** Detector: extract `scripts/lint/[a-z0-9_]+.py` +
backticked `no_*.py` mentions from all SKILL.md, test existence.
**Hits: 1** — prevent-regression's own `no_site_endpoint_sprawl.py`
mention, now explicitly marked not-shipped with a host-adapter slot (FP
post-repair). No siblings.

## Residual triage

- Class B siblings (3) → ledgered, batch sweep routing named (above).
- Verifier non-blocking observation (wiring "diff blocks" vs "staged
  copies" duality, spec-conformant) → ledgered as a tightening
  candidate. Nothing dropped.

## Ledger

Two `note` events appended to the `repair-skill` idea entry via
`track.py` (campaign result; residuals). Campaign record scrubbed: no
absolute identity paths, no source-host name (alias host-a only).

## End-state checks

- `scripts/skill_meta.py lint` → OK — 74 skills, 74 declaring new contract.
- `scripts/skill_comply/validate.py` → OVERALL PASS (6 fixtures);
  `git status scripts/skill_comply/` clean — harness untouched.
- Nothing committed (campaign constraint; commits are the human's move).

## Reply contract

Verifier: PASS (fresh-context sub-agent, refute brief; residual
limitation: same harness/session as implementer, and Stages 1–4 were
inline). Lift: P1 haiku pair B+1 V+1 G+1, no regressions. Dogfood: not
run — task-scaled loop; the machine-check lane (skill-comply C1–C9 ALL
PASS, 4/4 consequential) stood in as the execution-grounded check.
Residuals: 2, both ledgered with routing.
