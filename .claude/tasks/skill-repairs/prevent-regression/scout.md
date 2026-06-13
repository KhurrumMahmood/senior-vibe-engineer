# Scout — prevent-regression (Stage 2, inline)

> **Limitation.** Run INLINE by the campaign orchestrator (spend
> constraint), not by a fresh sub-agent — the two-independent-derivations
> property of the loop is degraded: the same eyes produced the review and
> this verification. Mitigation: every claim below is checked against
> commands actually run this session (ls, grep, `--help`) and quoted
> ground truth, not memory.

## 1. Claim verification

**F1 (missing `## How success is judged`) — TRUE.**
`grep -c "How success is judged" .claude/skills/prevent-regression/SKILL.md`
→ 0. The file has Phases 1–6 + Step 7 (multi-stage), confirming the
class-1 shape. The class-sweeps-spec row exists verbatim:
"prevent-regression | `.claude/skills/prevent-regression/SKILL.md:191` |
Verdict: guard artifact + verification recipe emitted; never installed
unilaterally" (class-sweeps-spec.md, Class 1 hit table). SKILL.md:191 is
`## Phase 1 — Pattern discovery` — the first pipeline header, matching
the spec's citation convention.

**F2 (write-site contradiction) — TRUE.** Quoted ground truth:
- SKILL.md:14-15 (description): "Read-only against production code —
  never installs the guard unilaterally; the human reviews and executes."
- SKILL.md:46-48: "Invocation does **not** authorize rolling the rule
  out. The skill produces a **proposal** under
  `reports/prevent-regression/<id>/` and stops."
- SKILL.md:217: "**Post:** `scripts/lint/<rule>.py` exists and is
  smoke-tested." (no staging location named)
- SKILL.md:291-293: "**Post:** `.pre-commit-config.yaml` has a `local`
  hook entry for the rule; `.github/workflows/ci.yml` has a diff-scoped
  step…"
- SKILL.md:321-322: "**Post:** `.claude/CLAUDE.md` has a new bullet…"
- SKILL.md:396-397: "Next recommended action: `git add` + commit, or
  abort if verification failed." — implies tree already modified.
Harness ground truth (read-only): `scripts/skill_comply/install_proposal.py`
docstring — "A proposal directory must contain `proposal_manifest.json`…
Paths in the manifest are relative to the proposal directory" and it
"copies the proposal's rule script and fixture pair into the repo's
`scripts/lint/` and `tests/lint/`, then applies the wiring edits". The
machine-grading path expects guard artifacts inside the proposal dir;
the human-install step applies wiring. F2's correction folded into the
spec: the staging contract must allow the Phase 6 telemetry append
(`reports/_meta/effectiveness.jsonl`, SKILL.md:374) — phrase the
constraint as "no guard artifact or wiring edit lands in the working
tree", not "nothing outside the proposal dir is written".

**F3 ("Three forms" routes four) — TRUE.** SKILL.md:59 "Three forms.
Detect and route:"; Form headers at :61 (A), :73 (B), :83 (C), :88 (D).

**F4 (empty `knowledge/`) — TRUE.**
`ls -la .claude/skills/prevent-regression/knowledge/` → empty (total 0).
SKILL.md:50-53: "Procedural detail lives in three knowledge files: —
`knowledge/` — shared conventions (points at
`_common/skill-conventions.md`) plus custom-lint patterns we've adopted."
SKILL.md:415: "`knowledge/ └── (host-overlay specifics).md  # pointer to
_common + skill-local rules`". `_common/skill-conventions.md` exists
(verified). The "three" count is also off-shape: the list mixes a dir,
an agent brief, and two scripts.

**F5 (`no_site_endpoint_sprawl.py` absent) — TRUE.**
`ls scripts/lint/no_site_endpoint_sprawl.py` → No such file. SKILL.md:232-235:
"For JS lexical guards, mirror the `no_site_endpoint_sprawl.py` shape:
suffix expansion, template-literal/string-concat matching, blockable
comments, and a reason-required `// noqa`." `silent_catch.py` (the Python
reference, SKILL.md:232) DOES exist in `scripts/lint/`.

## 2. Edit anchors

- F1+F2: insert after SKILL.md:48 ("…The human reviews and executes."),
  before :50 ("Procedural detail lives in three knowledge files:").
- F2 (Step 7): SKILL.md:396-397, the "Next recommended action" bullet.
- F3: SKILL.md:59, the words "Three forms".
- F4: SKILL.md:50-53 (intro bullet) and :414-416 (layout tree lines).
- F5: SKILL.md:232-235, the sentence beginning "For JS lexical guards".

## 3. Script contracts (derived live via --help)

- `verify_rule.py --rule R --bad B --good G [--expected-bad-hits N]`;
  exit 0 = BAD_RC=1 & GOOD_RC=0; exit 1 = fixture misbehaves; exit 2 =
  invocation error. Stdlib-only. Matches SKILL.md Phase 3 usage exactly.
- `generate_rule.py --rule-name N --intent I --output O [--force]`;
  scaffolds CLI-contract-conformant rule with TODO matcher. Matches the
  SKILL.md:55 listing ("rule scaffold generator (Phase 2)").
- Harness (read-only context for F2): `install_proposal.py --proposal D
  --repo R` (needs `proposal_manifest.json`); `score_conformance.py
  --proposal --repo --anchor --rule-name --fixed-files
  [--antipattern-files] [--recall-files]`, checks C1–C9. The manifest is
  harness orchestration glue — NOT a skill output mandate; the repair
  must not add it to the skill.

## 4. Pointer + artifact-drift audit

| Reference (SKILL.md) | On disk | Verdict |
|---|---|---|
| `agents/rule-designer.md` (:54) | exists | OK |
| `scripts/generate_rule.py` / `verify_rule.py` (:55) | exist, contracts match | OK |
| `knowledge/` content (:50-53, :415) | empty dir | DRIFT → F4 |
| `_common/skill-conventions.md` (:212) | exists | OK |
| `silent_catch.py` reference impl (:232) | `scripts/lint/silent_catch.py` exists | OK |
| `no_site_endpoint_sprawl.py` (:233) | missing | DRIFT → F5 |
| `scripts/lint/path_utils.py` (:225) | exists | OK |
| `scripts/lint/run.py` RuleSpec (:311-315) | exists, has RuleSpec | OK |
| `scripts/log_effectiveness.py` (:375) | exists | OK |
| `tests/lint/<rule>_{bad,good}` (:240 etc.) | destination paths, not refs | OK given F2 fix |
| https://docs.astral.sh/ruff/rules/ (:200) | external | not checked |

## 5. Load-bearing audit

- `pattern.md` (Phase 1 Post) → consumed by Phase 2 (AST shape source,
  per generate_rule.py docs "fill in based on pattern.md") and the
  proposal's Pattern section. Load-bearing.
- fixture pair + `verify_rule.py` report (Phase 3) → consumed by Phase 6
  Verification section and the harness's C3. Load-bearing.
- wiring (Phase 4) + CLAUDE.md bullet (Phase 5) → consumed by Phase 6
  Artifacts section / human install. Load-bearing.
- `proposal.md` + `effectiveness.jsonl` (Phase 6) → consumed by Step 7
  reply and the skill-effectiveness telemetry surface. Load-bearing.
- No ceremony stage found (consistent with the Class-2 sweep, which
  read prevent-regression and reported no hit).
