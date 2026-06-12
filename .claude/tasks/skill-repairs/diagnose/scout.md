# Scout report — /diagnose skill repair

Date: 2026-06-12. Read-only scout pass. Sources read in full:
`.claude/skills/diagnose/SKILL.md` (191 lines — review says "192", trivially
off by one), `scripts/evidence_gate.py` (297 lines),
`reports/skill-frame-review/diagnose.md` (the defect spec).

Directory verification: `.claude/skills/diagnose/` contains **only
`SKILL.md`** — no `knowledge/`, no `scripts/` subdir. Review preamble claim
confirmed TRUE.

---

## 1. Claim verification (F1–F6)

### F1 — root cause assertable with zero discriminating artifact — **TRUE**

- **Claim: Phase 4 never defines what confirms a hypothesis.** TRUE. Phase 4
  is lines 108–120. Line 110: `Probe one hypothesis at a time. Use the least
  noisy tool that can falsify it:` — it lists probe tools (lines 113–116) and
  the DIAG-prefix rule (118–120). No confirmation standard appears there or
  anywhere else in the file.
- **Claim: Phase 6 line 143 asks only for one sentence.** TRUE, exact line:
  - Line 143: `- write the root cause in one sentence;`
- **Claim: the only gate is `evidence_gate.py check` at line 180 and
  `_check_paths` tests existence only.** TRUE.
  - SKILL.md line 180: `.venv/bin/python scripts/evidence_gate.py check --skill diagnose --scan-dir reports/diagnose/scan-<TS>`
  - `evidence_gate.py` `_check_paths` is lines 67–82 (review's line range is
    exact). Per token it checks: declared path is a non-empty string
    (line 72), resolves relative to scan-dir (lines 75–77), then line 78:
    `if not candidate.exists():` → `missing_file`; else `ok` (line 81). It
    never opens or reads any file. **No content inspection anywhere in the
    script.** A one-sentence `root-cause.md` passes.

### F2 — confirmation without elimination — **TRUE**

- **Claim: Phase 3 mandates 3–5 ranked hypotheses.** TRUE. Lines 97–98:
  `Before probing, write three to five ranked hypotheses. Each one must be
  falsifiable:` (template at 100–102; boundary list at 104–106 — review said
  "104–107", off by one).
- **Claim: Phase 4 has no exit condition; nothing requires H2–H5 be falsified
  or downgraded before Phase 5.** TRUE. Phase 4 ends at line 120 (`...grep
  for the prefix in the cleanup phase.`); line 122 is `## Phase 5 - Fix`,
  which opens directly with regression-test/seam instructions. No gate, no
  acceptance criterion, no mention of remaining hypotheses anywhere
  (grep for "hypothes" hits only lines 95, 97, 104, 110).

### F3 — no Phase 0 evidence inventory / reporter-theory quarantine — **TRUE**

Phase 0 is lines 47–58. The complete bullet list (lines 51–55):

```
- the user-visible symptom;
- what "fixed" would look like;
- affected subsystem/workflow, if known;
- whether the risk triggers include production, customer impact,
  performance, data corruption, or intermittency.
```

Plus the glossary note (57–58). There is no "evidence already in hand" bullet
and no "reporter's suspected cause" bullet. Confirmed exactly as the review
states.

### F4 — no probe-loop stop condition, no back-edges — **TRUE**

- **Claim: `max_overhead` covers only the no-loop case.** TRUE. Line 32
  (frontmatter), verbatim: `max_overhead: "Stop after 30 minutes without a
  credible loop; write what was tried and what artifact/access is missing."`
  This scopes to Phase 1 (loop-building); once a loop exists nothing bounds
  Phases 3–4.
- **Claim: no instruction when all hypotheses are falsified; no return path
  when Phase 6 re-verification fails.** TRUE. Grep for "return", "back",
  "cycle", "fail" in SKILL.md: no phase defines a back-edge. Phase 6
  (lines 135–148) assumes verification succeeds — line 139 says rerun the
  loop, but no branch exists for the rerun still failing.

### F5 — gate run is ceremony; index omits core sections — **TRUE** (both halves)

- **(a) "Then run:" feeds nothing.** TRUE. Lines 177–181:
  line 177 `Then run:`, then the bash block (179–181) with the check command.
  The skill never says the gate must pass, never mentions exit codes, never
  requires the result in the reply, and nothing after line 181 references the
  gate. **Repo-level confirmation:** nothing in `.github/`, `scripts/`, or
  `.pre-commit-config.yaml` invokes `evidence_gate.py` (grepped); the
  script's own docstring (lines 26–27) says "PR F will wire this into CI; PR
  G will turn the warnings into hard refusals" — neither happened. Soft gate,
  unconsumed at every level.
- **(b) Diagnosis Index Shape omits Root Cause and Reproduction.** TRUE.
  Section heading at line 183; template lines 185–191, verbatim body:

  ```markdown
  # Diagnosis: <symptom>

  ## Symptom
  ## Fix
  ## Prevention follow-up
  ```

  No `## Root cause`, no `## Reproduction`. The review's quoted shape matches
  exactly.

### F6 — reproduction/verification claimable by assertion — **TRUE** (two off-by-one line cites)

- "Run the loop enough times to trust it." is **line 83**, not 82.
- "rerun the original loop and the minimized regression" — line 139, exact.
- "it is deterministic, or the reproduction rate is high enough to debug;" is
  **line 88**, not 89.
- **Claim: `reproduction.md` and `verification.md` are content-unconstrained
  and gate-checked for existence only.** TRUE. SKILL.md never states any
  required content for either file (in fact it never instructs writing them
  by name at all — see §4, drift D1). The gate's `_check_paths` is
  existence-only (see F1). No numerator/denominator is recorded anywhere for
  the intermittent case.

**Tally: 6 TRUE, 0 PARTLY, 0 FALSE.** Only cosmetic errata: file is 191 lines
not 192; F6's "line 82"→83 and "line 89"→88; F1/F2 boundary-list cite
"104–107"→104–106. One inaccuracy in the review's *praise* (not a finding):
it says the `[DIAG-]` tag is "consumed by the Phase 6 cleanup grep and
`cleanup-check.md`" — `cleanup-check.md` is never mentioned in any phase body
(see D2 below), so that chain is weaker than the review credits.

---

## 2. Edit anchors (smallest-fix landing sites)

All paths: `~/Projects/engineering-skills/.claude/skills/diagnose/SKILL.md`.

**F1 — root-cause proof standard.** Two anchors:
1. Phase 6 bullet, line 143. Surrounding text (lines 141–144):
   ```
   - remove every `[DIAG-...]` probe;
   - delete throwaway harnesses or move them under an explicit report path;
   - write the root cause in one sentence;
   - answer: what would have prevented this?
   ```
   Replace/extend the line-143 bullet to require: the satisfied falsifiable
   statement from Phase 3 + the confirming probe's exact command + pasted
   observed output (or cause-toggle demonstration) **in `root-cause.md`**.
2. Optionally the Evidence Manifest section, between the JSON block (ends
   line 175, `}` then ``` ` ``` ) and `Then run:` (line 177) — a short
   "required content per evidence file" block lands cleanly here and also
   carries F6.

**F2 — elimination gate before Phase 5.** Anchor: end of Phase 4, between
line 120 and line 122. Surrounding text:
```
Every temporary debug line must include one unique prefix such as
`[DIAG-YYYYMMDD-a1]`. Remove it before done, and grep for the prefix in
the cleanup phase.

## Phase 5 - Fix
```
Insert the gate paragraph ("before fixing, name each remaining hypothesis and
the observation that rules it out; un-ruled-out hypotheses go in
`root-cause.md` as residual uncertainty") as the final paragraph of Phase 4.

**F3 — Phase 0 bullets.** Anchor: after line 55. Surrounding text (54–58):
```
- whether the risk triggers include production, customer impact,
  performance, data corruption, or intermittency.

If the symptom uses fuzzy domain language, resolve it against the host
project's glossary before writing tests or probes.
```
Insert two bullets after the risk-triggers bullet: "evidence already in hand
(tracebacks, logs, prior attempts, exact commands)" and "reporter's suspected
cause, recorded as one hypothesis among several, never as a finding."

**F4 — back-edges + two-cycle stop.** Two anchors:
1. Same insertion point as F2 (end of Phase 4, before line 122): the
   all-hypotheses-falsified back-edge ("return to Phase 3, re-rank with new
   observations; after two full cycles without a confirmed cause, stop and
   write the eliminated space as partial findings").
2. Phase 6, after the bullet list / before line 146. Surrounding text
   (lines 144–148):
   ```
   - answer: what would have prevented this?

   If the answer is "a lint/test/pattern would have caught it", recommend
   `/prevent-regression`. If the answer is "the code had no durable test
   surface", recommend the matching EXPLAIN or REFACTOR skill.
   ```
   Insert before line 146 (or as a new bullet after line 139): "If Phase 6
   verification fails, the root cause is unconfirmed — return to Phase 3; do
   not patch the fix."
   Optionally extend frontmatter `max_overhead` (line 32) to name the
   two-cycle bound.

**F5a — gate must pass.** Anchor: directly after the bash block, lines
179–181 / before line 183 `## Diagnosis Index Shape`. Surrounding text:
```
Then run:

```bash
.venv/bin/python scripts/evidence_gate.py check --skill diagnose --scan-dir reports/diagnose/scan-<TS>
```

## Diagnosis Index Shape
```
Insert: "The gate must exit 0. On exit 1, fix the missing evidence and
re-run. Paste the gate's summary line in your final reply."

**F5b — index shape sections.** Anchor: lines 185–191 markdown block. Add
`## Reproduction` and `## Root cause` between `## Symptom` and `## Fix`
(exact ordering is implementer's choice; both must appear).

**F6 — transcript-bearing evidence files.** Anchors:
1. Phase 2, after the confirm list / minimization paragraph (lines 92–93):
   ```
   Minimize only while preserving the real failure mode. A tiny test that
   does not exercise the production call path is a trap, not evidence.
   ```
   Add: `reproduction.md` must embed the exact loop command and one pasted
   failing run; for intermittent symptoms, record observed fail-rate as
   N-failures / M-runs.
2. Phase 6 bullet line 139 (`- rerun the original loop and the minimized
   regression;`): extend to "…and paste the passing rerun output of the same
   command into `verification.md`."
3. Or carry both in the single Evidence Manifest content block named under
   F1 anchor 2 — one block can serve F1+F6 together (smallest total diff).

---

## 3. Script contract — `scripts/evidence_gate.py`

**Invocation shape:** `evidence_gate.py [--skills-dir DIR] {check|init|show} ...`
- Global flag: `--skills-dir` (default `<repo>/.claude/skills`, line 40/270).
  Note it is a *pre-subcommand* global argument.
- `check --skill <name> --scan-dir <path> [--json]` (lines 274–278) —
  validate manifest vs frontmatter.
- `init --skill <name> --scan-dir <path> [--force] [--json]` (lines 280–285)
  — scaffold `evidence.json` stub with empty-string paths per token
  (lines 214–221); refuses to overwrite without `--force` (lines 206–212).
- `show --skill <name> [--json]` (lines 287–290) — print
  `evidence_required` / `produces` / `consumes` from frontmatter.

**Exit codes** (docstring lines 20–23, verified in code):
- `0` — pass / no requirements (lines 116–129, 197–203) / scaffold ok.
- `1` — evidence token missing or declared file not found (line 180), no
  manifest at all (line 147), or init refusing to overwrite (line 212).
- `2` — usage errors: unknown skill / bad frontmatter (lines 104–106),
  scan-dir absent (lines 109–111), malformed/non-object manifest JSON
  (lines 149–156).

**Files expected:**
- `<skills-dir>/<skill>/SKILL.md` with YAML frontmatter (parsed via
  `scripts/_lib/yaml_frontmatter.read`, line 46 — file exists, needs the
  venv's PyYAML).
- `<scan-dir>/evidence.json` (constant `MANIFEST_FILENAME`, line 41): a JSON
  object whose `evidence` key maps each `evidence_required` token to a path,
  interpreted **relative to scan-dir** unless absolute (lines 75–77). Other
  manifest keys (`skill`, `scan_id`, `produced_at`, `notes`) are written by
  `init` but **ignored** by `check`.

**For /diagnose specifically:** frontmatter line 30 declares
`evidence_required: [reproduction_or_reason, root_cause, fix_verification,
cleanup_check]`; the SKILL.md JSON example (lines 164–175) maps them to
`reproduction.md`, `root-cause.md`, `verification.md`, `cleanup-check.md` —
token set matches frontmatter exactly. The example omits
`produced_at`/`notes` vs the `init` stub; harmless since `check` ignores
them.

**Where a content check would land (do NOT write code; placement only):**
- Natural seam: in `cmd_check`, immediately after `rows = _check_paths(...)`
  (line 162) — a second pass (`_check_content`) that, for tokens whose path
  row is `ok`, reads the file and applies per-token rules, downgrading the
  row to a new status such as `missing_content` (which then fails the
  `ok_total == len(required)` pass test at line 164 automatically, and needs
  one new branch in `_render_text`, lines 85–97).
- Rules must be data-driven, not hardcoded to /diagnose, to keep the script
  generic. Two viable shapes: (a) a module-level per-token rule table, or
  (b) an optional frontmatter key (e.g. `evidence_content:` mapping token →
  required-marker list) read alongside `evidence_required` in
  `_required_tokens`' neighborhood. Shape (b) keeps the contract declared in
  the skill, consistent with the existing frontmatter-driven design.
- **Minimal implementable checks** (pure stdlib, regex-grade, no semantics):
  - `root_cause` → file contains at least one fenced code block
    (`` ``` `` pair) **and** a `[DIAG-` tag occurrence (probe transcript
    proxy), and/or an `If ` … ` then ` falsifiable-statement line.
  - `reproduction_or_reason` → at least one fenced code block (the loop
    command + failing output); optionally an `N/M` fail-rate token when
    intermittent — the intermittent qualifier is NOT machine-knowable, so
    keep that part prose-mandated in SKILL.md, not script-enforced.
  - `fix_verification` → at least one fenced code block (passing rerun).
  - `cleanup_check` → contains `[DIAG-` (the grep command/result will
    reference the prefix) or a `grep` invocation line.
  These are weak-but-unfakeable-by-omission proxies: they cannot prove truth
  but they make "one plausible sentence" fail the gate, which is the F1/F6
  bar.
- **Test gap:** there are NO existing tests for `evidence_gate.py` anywhere
  under `tests/` (grepped `tests/` and `tests/scripts/`). Any content-check
  change lands without coverage unless a test module is added — per the repo
  Verification Policy a normal code change needs a named suite, so the
  implementer should budget a new `tests/scripts/test_evidence_gate.py` (or
  state the gap).
- Other consumers to not break: `adapt-project`, `project-interview`, and
  `plan-skill` SKILL.md files also reference `evidence_gate` — content rules
  must default to "no rule declared → path check only" so those skills are
  unaffected.

---

## 4. Pointer + artifact-drift audit

Every reference in SKILL.md checked against reality:

| Reference (line) | Status |
|---|---|
| `reports/diagnose/scan-<TS>/diagnosis.md` (41) | Output path pattern; `reports/diagnose/` doesn't exist yet (no runs) — fine, created at runtime. Matches skill-catalog.md line 215's description. |
| `.venv/bin/python` (43, 180) | Exists. |
| `CONTEXT.md` (44) | Exists at repo root. |
| "host project's glossary" (58) | Vague but real surface — `.claude/contracts/concepts.yaml` exists. Not drift. |
| `scripts/evidence_gate.py check --skill diagnose --scan-dir …` (180) | Script exists; subcommand and both flags exist in argparse; command is valid as written. |
| Manifest tokens vs frontmatter `evidence_required` (30 vs 164–175) | Exact match, all four tokens. |
| `/prevent-regression`, `/fix-workflow`, `/refactor-subsystem`, `/gut-check`, `/architecture-fit` (frontmatter + Phase 6) | All exist as installed skills. |
| `allowed-tools: Bash, Read, Grep, Glob, Write, Edit` (5) | Consistent with body (bash gate command, file writes). |

**New defects found (drift the review did not name):**

- **D1 — Four of five evidence files are artifacts no phase produces.** The
  tree (lines 154–162) and JSON (164–175) require `reproduction.md`,
  `root-cause.md`, `verification.md`, `cleanup-check.md`, but no phase body
  ever instructs writing any of them *by filename*. Phase 1 line 77 says
  "write `reproduction_or_reason`" — a frontmatter *token*, not a file.
  Phase 6 line 143 says write the root cause "in one sentence" with no
  destination file named. `verification.md` and `cleanup-check.md` have no
  producing instruction at all. An executor reaches the Evidence Manifest
  section having been told to create only `diagnosis.md` (line 41). The F1/F6
  fixes should name the files at the producing phases, which repairs D1 as a
  side effect.
- **D2 — `cleanup_check` evidence is declared but unwired.** Phase 4
  (119–120) says "grep for the prefix in the cleanup phase" and Phase 6
  line 141 says "remove every `[DIAG-...]` probe", but nothing says to record
  the grep result in `cleanup-check.md`. The review's praise section
  *overstates* this chain as already load-bearing; it is half-wired
  (tag→grep exists; grep→artifact does not).
- **D3 — `produces: [diagnosis_report, reproduction_loop, regression_test]`
  (line 29) is conditionally false.** Phase 5 (lines 124–130) makes the
  regression test conditional on "a correct seam" existing; when no seam
  exists the skill explicitly ships without one. Minor frontmatter/body
  tension; fix is either "regression_test (or seam-gap finding)" phrasing or
  leave as-is — flag for implementer judgment.
- **D4 — The gate's own promise of future enforcement is stale.** Docstring
  lines 26–27: "PR F will wire this into CI; PR G will turn the warnings into
  hard refusals where appropriate." Neither exists anywhere in the repo
  (no CI/hook references to `evidence_gate`). Not a SKILL.md defect, but
  context the implementer should know: the SKILL.md-side "gate must pass +
  paste summary" fix (F5a) is currently the ONLY enforcement available.

---

## 5. Load-bearing audit (what consumes each mandated step's output)

| Mandated step | Declared output | Consumer | Verdict |
|---|---|---|---|
| Phase 1 abort path (77–79): write `reproduction_or_reason` with what was tried | `reproduction.md` (via manifest) | `evidence_gate check` — existence only | Half load-bearing; content unconsumed (F6) |
| Phase 2 "run the loop enough times to trust it" (83) + 4 confirm bullets (87–90) | none recorded | nothing | **Ceremony as written** (F6 fixes it: transcript into `reproduction.md`) |
| Phase 3 ranked falsifiable hypotheses (97–102) | none recorded (no file named) | implicitly Phase 4 probing order | Half load-bearing; never re-consumed at accept time (F2) |
| Phase 4 `[DIAG-]` unique prefix (118–120) | tagged debug lines | Phase 6 line 141 removal + grep | Load-bearing in-skill; recording surface (`cleanup-check.md`) unwired (D2) |
| Phase 6 rerun loop + regression (139) | none recorded | nothing | **Ceremony as written** (F6: paste into `verification.md`) |
| Phase 6 narrowest touched tests (140) | none recorded | nothing | Ceremony; consistent with repo-wide verification policy, but unrecorded |
| Phase 6 root cause one-liner (143) | destination unnamed (presumably `root-cause.md`) | gate existence check only | **Ceremony-grade proof** (F1) |
| Phase 6 "what would have prevented this?" (144) | answer | lines 146–148 route to `/prevent-regression` or EXPLAIN/REFACTOR skill | **Genuinely load-bearing** — the one fully-wired step |
| Evidence gate run (177–181) | exit code + summary | nothing — no pass requirement, no reply mention, no CI | **Pure ceremony** (F5a) |
| Diagnosis Index (185–191) | `diagnosis.md` | human reader; `## Prevention follow-up` pairs with escalate_to | Half load-bearing; omits the two key outputs (F5b) |

Net: exactly one mandated step (`what would have prevented this?` →
recommendation routing) is fully wired end-to-end today. The F1/F2/F5/F6
fixes convert the other verification steps from assertion-grade to
transcript-grade, and the gate content-check (§3) gives them a mechanical
consumer.
