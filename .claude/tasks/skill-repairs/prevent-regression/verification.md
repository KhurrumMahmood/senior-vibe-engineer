# Verification — /prevent-regression repair (Stage 4)

> **Verifier provenance.** This report was produced by a fresh-context
> sub-agent verifier: no conversational context was shared with the
> implementer, and every claim below is grounded in files read and
> commands run this session (diff, grep, ls, live lint). **Residual
> independence limitation:** the verifier runs in the same harness and
> session as the campaign — it is a fresh context, not a fresh machine
> or a different model; treat the independence property as
> context-level, not infrastructure-level.

Materials judged: working-tree `.claude/skills/prevent-regression/SKILL.md`
(repaired) vs the frozen pre-repair copy at
`/tmp/skill-repairs-old/prevent-regression/SKILL.md`, against
`.claude/tasks/skill-repairs/prevent-regression/change-spec.md` with
`scout.md` as ground truth.

## Overall verdict: PASS

All five C-items RESOLVED. No invention found (one descriptive gloss
noted and verified true). No new defects of the swept classes. Live
lint passes. Two minor observations recorded; neither violates the
change spec — both are wording the spec itself dictated or permitted.

---

## Per-C-item verdicts

### C1 — `## How success is judged` block: RESOLVED

The frozen copy has no such section (`grep -c "How success is judged"`
on the frozen copy → 0; scout F1 confirmed). The repaired file inserts
it after the "…The human reviews and executes." paragraph and before
"Procedural detail lives beside this file:", exactly at the spec's
anchor. Five bullets — within the mandated 4–8. Each instantiates a
gate already mandated elsewhere in the body; **no new gates were
invented**:

- > "Guard artifact + verification recipe **emitted, never installed
  > unilaterally** — no guard artifact or wiring edit lands in the
  > working tree."

  Traces to the class-sweeps gate line quoted in scout §1 ("guard
  artifact + verification recipe emitted; never installed
  unilaterally") and the spec's scout-corrected constraint wording
  verbatim ("no guard artifact or wiring edit lands in the working
  tree").
- > "`verify_rule.py` reports BAD_RC=1, GOOD_RC=0 (Phase 3)."

  Matches Phase 3 body: "It must report BAD_RC=1 (violations fired)
  and GOOD_RC=0 (no false positives)." The "pasted, not asserted"
  qualifier traces to spec C1 ("BAD_RC=1/GOOD_RC=0 pasted (Phase 3)").
- > "Historical fire: the rule fires on each pre-fix site via
  > `git show <anchor>^:<file>` and is clean on current HEAD (Phase 6)."

  Matches the Phase 6 proposal template: "Historical regression: rule
  fires on `git show <anchor>^:<file>` for each pre-fix site. / Clean
  on current HEAD".
- > "The bad fixture covers every anti-pattern variant and the good
  > fixture proves the rule stays quiet on legitimate forms (Phase 3)"

  Matches Phase 3 body ("must contain **every variant** … must contain
  the legitimate patterns the rule must NOT flag") and Core belief 4.
- > "Test-only guards (Phase 3b): the focused regression module runs
  > green, with its run output in the proposal."

  Matches Phase 3b body: "run that module plus the baseline suite. The
  proposal still needs a pattern section, verification results…".

Refutation attempt (did the block invent gates?): the only clause not
anchored in the body is "the precision/recall gates a conformance
harness re-runs by side-effect" (bullet 4). It traces to the spec's
declared-verdict paragraph ("the shape `scripts/skill_comply/
install_proposal.py` installs from — checked by the machine-check lane
after Stage 5") and scout §3 (`score_conformance.py … checks C1–C9`).
It imposes no new obligation on a skill run — "by side-effect" states
that an external harness re-checks gates the run already owes — and,
critically, it does **not** smuggle `proposal_manifest.json` into the
output contract (grep for `manifest` in the repaired file → 0 hits),
upholding the spec's hard constraint.

### C2 — staging contract: RESOLVED

(a) The staging paragraph exists adjacent to the C1 block:

> "Guard artifacts are **staged, not installed**: author them under the
> proposal directory at their repo-relative destination paths
> (`reports/prevent-regression/<id>/scripts/lint/<rule>.py`,
> `reports/prevent-regression/<id>/tests/lint/<rule>_bad.<ext>`, …),
> and emit wiring (pre-commit hook, CI step, `run.py` RuleSpec,
> CLAUDE.md bullet) as ready-to-apply diff blocks inside `proposal.md`.
> The Phase Pre/Post conditions below name destination paths — read
> each as \"staged under the proposal directory at that relative path\"
> until the human installs."

This is the spec's C2(a) content near-verbatim, including the
scout-mandated constraint phrasing, which correctly keeps the Phase 6
telemetry append legal: the Phase 6 Post still reads
"`reports/_meta/effectiveness.jsonl` appended" — a report write, not a
"guard artifact or wiring edit", so no contradiction. The staged
paths (`<proposal-dir>/scripts/lint/<rule>.py`,
`<proposal-dir>/tests/lint/…`) are exactly the proposal-dir-relative
shape `scripts/skill_comply/install_proposal.py` installs from
(docstring: "Paths in the manifest are relative to the proposal
directory" / "copies the proposal's rule script and fixture pair into
the repo's `scripts/lint/` and `tests/lint/`"), so the Bucket-A output
contract stays scoreable.

(b) Step 7 last bullet replaced. Frozen: "Next recommended action:
`git add` + commit, or abort if verification failed." Repaired:

> "Next recommended action: human reviews the proposal, installs the
> staged artifacts and wiring diffs, and commits — or abort if
> verification failed."

`grep -n "git add"` on the repaired file → 0 hits.

(c) Phases not renumbered; Phases 2–5 bodies untouched (the diff shows
no hunks inside them except the C5 sentence in Phase 2).

Refutation attempt (leftover in-tree-write phrasing): swept the whole
file for `git add`, `wired`, and every `Post:` line. Remaining
destination-path Posts (Phase 2 "`scripts/lint/<rule>.py` exists",
Phase 4 "`.pre-commit-config.yaml` has a `local` hook entry", Phase 5
"`.claude/CLAUDE.md` has a new bullet"), the Phase 4 hook YAML, the
Phase 6 Artifacts list ("`.pre-commit-config.yaml` (modified)" etc.),
and Phase 5's "**Pre:** rule wired." all survive — but the spec's
C2(c) explicitly mandates leaving those bodies untouched, and the
staging paragraph's blanket read-rule ("read each as staged … until
the human installs") resolves each of them. The Phase 6 Artifacts list
is content of the emitted `proposal.md` (it describes what installing
will touch), not an instruction to edit the tree. No contradiction
that the spec did not itself accept.

Minor observation (not a defect): for wiring, the paragraph says "diff
blocks inside `proposal.md`" while the read-rule speaks of "staged
under the proposal directory at that relative path" — wiring has no
staged copy, only diff blocks. This wording duality comes verbatim
from spec C2(a) ("emitted as ready-to-apply diff blocks in
proposal.md; Phase Pre/Post conditions … read against the staged
copies"), so the implementer is spec-conformant; the residual
ambiguity belongs to the spec, not the repair.

### C3 — count fix: RESOLVED

Frozen line 59: "Three forms. Detect and route:". Repaired: "Four
forms. Detect and route:". Actual `### Form` headers counted by grep —
exactly four:

```
88:### Form A — Cluster ID from a recent scan
100:### Form B — Explicit pattern description
110:### Form C — `--dogfood <rule-name>`
115:### Form D — Product-topology guard template
```

### C4 — knowledge/ reality: RESOLVED

(a) Frozen intro: "Procedural detail lives in three knowledge files: —
`knowledge/` — shared conventions (points at
`_common/skill-conventions.md`) plus custom-lint patterns we've
adopted." Repaired:

> "Procedural detail lives beside this file:
>
> - `_common/skill-conventions.md` — shared conventions (symbolic
>   names, report shapes). `knowledge/` is a host-overlay slot for
>   custom-lint patterns the host project adopts; it ships empty in
>   this ecosystem."

The false "three knowledge files" framing is gone; the pointer goes
directly at `_common/skill-conventions.md` (verified on disk); the
`agents/rule-designer.md` and scripts bullets are kept unchanged.

(b) Layout tree: frozen had the phantom entry
"`knowledge/ └── (host-overlay specifics).md  # pointer to _common +
skill-local rules`". Repaired:

> "`├── knowledge/                       # host-overlay slot — ships empty;`
> "`│                                    # conventions live in _common/skill-conventions.md`"

Phantom file entry removed; annotation matches reality —
`ls -la .claude/skills/prevent-regression/knowledge/` → empty
(total 0), consistent with "ships empty".

Refutation attempt (other stale `knowledge/` references): grep
`knowledge` over the whole repaired file → exactly two hits, both the
corrected ones quoted above. Grep `three` (case-insensitive) → zero
hits anywhere in the file.

### C5 — host-only JS exemplar: RESOLVED

Frozen Phase 2: "For JS lexical guards, mirror the
`no_site_endpoint_sprawl.py` shape: suffix expansion, …". Repaired:

> "`silent_catch.py` is the Python reference implementation. For JS
> lexical guards (`no_site_endpoint_sprawl.py` was the source host's
> exemplar — not shipped in this ecosystem;
> `<!-- host-adapter: point at a local JS lexical rule exemplar when one exists -->`),
> keep this shape: suffix expansion, template-literal/string-concat
> matching, blockable comments, and a reason-required `// noqa`."

All four spec requirements hold: `silent_catch.py` kept as Python
reference (verified to exist at `scripts/lint/silent_catch.py`);
`no_site_endpoint_sprawl.py` marked as a source-host rule not shipped
(verified absent: `ls scripts/lint/no_site_endpoint_sprawl.py` → No
such file); explicit `<!-- host-adapter: ... -->` slot present; the
portable shape description survives as the normative content ("keep
this shape: …"). Coherence: the sentence parses cleanly — the
parenthetical isolates the host-history note and adapter slot, and the
imperative "keep this shape" carries the rule. Readable, if dense.

## No-invention diff audit

`diff -u` of frozen vs repaired shows exactly five hunks (intro
staging paragraph + success block + pointer-list rewrite + "Four
forms"; Phase 2 C5 sentence; Step 7 bullet; layout tree). Every added
sentence traced:

| Added text | Traces to |
|---|---|
| Staging paragraph ("staged, not installed … until the human installs") | Spec C2(a), near-verbatim, incl. scout's constraint wording |
| `## How success is judged` heading + bullet 1 | Spec C1 + class-sweeps gate line quoted in scout §1 + spec C2(a) constraint phrase |
| Bullet 2 (verify_rule, "pasted, not asserted") | Pre-existing Phase 3 text + spec C1 ("pasted") |
| Bullet 3 (historical fire / clean HEAD) | Pre-existing Phase 6 Verification template |
| Bullet 4 (fixture coverage; "conformance harness re-runs by side-effect") | Pre-existing Phase 3 text + Core belief 4; harness clause → spec declared-verdict + scout §3 |
| Bullet 5 (Phase 3b run green, output in proposal) | Pre-existing Phase 3b text ("verification results") |
| "Procedural detail lives beside this file" rewrite | Spec C4(a) |
| "(symbolic names, report shapes)" gloss | "symbolic names" → pre-existing SKILL.md Phase 1 text ("Use symbolic names in prose — see `_common/skill-conventions.md`"); "report shapes" → not in the three allowed sources, but verified TRUE against the referenced file's own headers ("Report directory layout", "No raw line numbers in prose" / symbolic references). Descriptive gloss of a real file, not a claim or mandate — noted, not flagged as invention. |
| "Four forms." | Spec C3 |
| C5 sentence (host exemplar + adapter slot) | Spec C5 + scout F5 ("the source host's" exemplar framing) |
| Step 7 bullet | Spec C2(b) |
| Layout-tree comments | Spec C4(b) |

No added claim traces to none of the sources. Constraint upheld:
`proposal_manifest.json` is nowhere in the repaired file.

## New-defect sweep (same classes, whole file)

- **Count drift:** "Four forms" vs 4 `### Form` headers — exact. Core
  beliefs numbered 1–11 sequentially. Phase 6 Pre "Phases 1–5
  complete" — Phases 1–5 all present. No "three"/"five"-style counts
  remain anywhere (grep). No drift.
- **Phantom references:** every path the diff touches or the file
  names verified on disk: `_common/skill-conventions.md`,
  `agents/rule-designer.md`, `scripts/generate_rule.py`,
  `scripts/verify_rule.py`, `scripts/lint/silent_catch.py`,
  `scripts/lint/path_utils.py`, `scripts/lint/run.py`,
  `scripts/log_effectiveness.py` — all exist. `knowledge/` exists and
  is empty, matching its new "ships empty" annotation.
  `no_site_endpoint_sprawl.py` is absent and is now explicitly
  described as absent. The removed phantom
  `(host-overlay specifics).md` does not reappear. No phantom
  references.
- **Staging contradictions:** swept `git add` (0 hits), `wired`/`wire`
  (remaining hits are the `--dogfood` rewire forms, the Phase 4 title,
  and Phase 5's "Pre: rule wired" — all covered by the blanket
  read-as-staged rule and protected by spec C2(c)'s
  bodies-untouched constraint), and all six `Post:` lines (destination
  paths, explicitly re-scoped by the staging paragraph). The Phase 6
  telemetry append remains legal under the chosen constraint wording.
  No internal contradiction introduced.

## Live lint

```
$ .venv/bin/python scripts/skill_meta.py lint
OK — 74 skills, 74 declaring new contract
```

Exit code 0.

## Conclusion

PASS. C1–C5 all RESOLVED with quoted evidence; the diff contains no
invented claims (one true descriptive gloss noted); no new defects of
the swept classes; lint passes live. Working tree shows only
`.claude/skills/prevent-regression/SKILL.md` modified under the skill
directory (+41/−11), and nothing was committed — consistent with the
campaign's no-commit constraint.
