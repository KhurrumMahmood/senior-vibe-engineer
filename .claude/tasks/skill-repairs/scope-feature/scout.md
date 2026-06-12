# SCOUT report — /scope-feature repair

Date: 2026-06-12. Read-only pass over
`.claude/skills/scope-feature/SKILL.md` (272 lines, last modified
May 13), `knowledge/structure-redesign-lessons.md`, `scripts/plans.py`,
`scripts/decisions.py` CLI surface, and
`reports/skill-frame-review/scope-feature.md` (defect spec). All line
numbers below are from the current SKILL.md.

---

## 1. Claim verification (F1, F2, F3, F4, F6)

### F1 — "Stage 5 verifies with `plans.py audit`, which checks parse, not the contract property" — TRUE (and understated)

SKILL.md Stage 5 (lines 229–238):

> ### Stage 5 — Advance status
>
> Edit `${PLAN_PATH}` to set `status: scoped` (in-place, single
> `status:` line in frontmatter).
>
> ```bash
> python3 scripts/plans.py audit
> ```
>
> Confirm the plan loads cleanly.

What `cmd_audit` / `_audit_drift` actually check (`scripts/plans.py`
lines 314–349):

1. `status` is in `VALID_STATUSES` (line 317–318).
2. If `status == "promoted"`: `successor_spec` is set and the spec
   file exists (lines 319–324).
3. If `motivating_decision` is set: a matching ADR file exists
   (lines 325–329).

That is the entire check list. Nothing inspects §1/§2 body content,
placeholder text, scope specificity, or any contract property. The
review's "checks parse" is actually *generous*: a plan whose
frontmatter fails to parse is **skipped with a stderr warning** in
`load_plans` (lines 76–80, `print(f"warning: skipping {path.name}...`)
and produces **no drift diagnostic** — `audit` can exit 0 even when
the just-edited plan didn't load at all. Also note `audit` is
**registry-wide**, not scoped to `${PLAN_NAME}`: drift in an unrelated
plan makes it exit 1, and cleanliness of unrelated plans makes it exit
0 regardless of this plan's body. Belief 1 (lines 50–53, "a sub-agent
two months from now can tell whether a proposed change is in-scope")
has no test anywhere in the pipeline. **Verdict: TRUE.**

### F2 — "Core beliefs sit ~200 lines above Stage 4; no re-activation at the write site" — PARTLY (number off; substance true)

- `## Core beliefs` heading: line 48; belief 1 ends line 53.
- `### Stage 4 — Write §1-2 of the plan`: line 196; template block
  lines 202–227.

Actual distance: ~143–148 lines (48→196), not "~200". The substance
is verified true: the Stage 4 text (lines 198–200) is purely
mechanical —

> Edit `${PLAN_PATH}` to fill §1 (Scope & Bounds) and §2 (Success
> Criteria) with the user's answers and the prior-constraint cross-
> references. Use this shape:

— and the markdown template (lines 202–227) contains only structural
placeholders (`_Concrete artifact 1_`, `_Observable outcome 1 (with
metric / fixture)_`). No gate question, no restatement of the
adjudication standard, anywhere in Stage 4. **Verdict: PARTLY
(line-count claim inexact; frame-decay claim true).**

### F3 — "Tier check (Q6) is placed after all five scoping questions" — TRUE

Stage 2 questions run in order at lines 110–165. Q6 is the last
(lines 162–165):

> 6. **Tier check.** Re-read the user's answers. Does this look
>    System-tier (cross-subsystem, multi-week, new subsystem) or has it
>    actually shrunk to Feature-tier? If Feature-tier — STOP, recommend
>    `/plan-feature` instead, mark plan `abandoned`.

Q1 (lines 110–112) has no provisional tier signal:

> 1. **One-sentence problem statement.** "Right now, X happens / does
>    not happen, and that costs Y." If the user can't write this in one
>    sentence, the work is too vague — push back.

The only earlier tier mention is frontmatter `escalate_to` (lines
20–24) and belief 3 (lines 57–61) — neither is wired into the Q1–Q5
flow. **Verdict: TRUE.**

### F4 — "No phase-0 inventory for context-rich invocations" — TRUE

Stage 0 (lines 78–93) is purely mechanical setup (path vars, scaffold,
status guard). Stage 2 opens (lines 110–111):

> Pose the user the following questions in order. Stop after each round
> and wait for the answer; do not invent answers.

There is no step anywhere in the pipeline that inventories what the
invoking conversation already answers vs. what must still be asked.
Grep confirms: no occurrence of "conversation", "already answered",
"inventory", or any phase-0 / Stage 0.5 construct. **Verdict: TRUE.**

### F6 — "Read … end-to-end with no acknowledgment artifact" — TRUE

Stage 1, lines 105–107 (exact text):

> Read `.claude/docs/canonical-patterns.md` and
> `.claude/docs/architectural-smells.md` end-to-end. These are the law-as-
> stated; scope must respect them.

No required output, no named-priors line, no artifact of any kind
proves the read happened. The first downstream surface that *implies*
the read is Stage 3's checklist (lines 179–188) and the §1 "Prior
constraints" template rows (lines 217–220) — but an executor can fill
those from skim/recall without the end-to-end read. **Verdict: TRUE.**

(F5 is a cross-skill specimen about /track-idea; per repair brief it
yields only the design rule "every mandated stage must be load-bearing"
— applied in §5 below. No direct scope-feature edit.)

---

## 2. Edit anchors (exact, for Edit-tool anchoring)

### F1 — insert Stage 4.5 artifact-truth gate

Land **between** the end of the Stage 4 template code fence (line 227,
the closing ```` ``` ````) and the Stage 5 heading. Anchor on the
unique Stage 5 opening:

```
### Stage 5 — Advance status

Edit `${PLAN_PATH}` to set `status: scoped` (in-place, single
`status:` line in frontmatter).
```

Insert a `### Stage 4.5 — Artifact-truth gate` section before this:
generate three hypothetical borderline changes (plausible, adjacent,
not user-supplied), adjudicate each strictly from the §1 text written
in Stage 4 **without asking the user**; if any adjudication is
ambiguous, tighten §1 and re-test before advancing status. Renumber
nothing — 4.5 slots in.

### F2 — gate question embedded inline in the Stage 4 template

Two viable anchor points; smallest fix uses both lightly:

(a) The lead-in sentence (lines 198–200), unique text:

```
Edit `${PLAN_PATH}` to fill §1 (Scope & Bounds) and §2 (Success
Criteria) with the user's answers and the prior-constraint cross-
references. Use this shape:
```

(b) Inside the template itself, the `**In scope.**` block (lines
206–208):

```
**In scope.**
- _Concrete artifact 1_
- _Concrete artifact 2_
```

Embed the gate as a comment/instruction at the write site, e.g. a
line in the template such as
`<!-- gate: each bullet must let a stranger adjudicate a borderline change in/out -->`
or an imperative sentence appended to the lead-in. This re-states
belief 1 at the moment of writing (run-0004 mechanism).

### F3 — provisional tier flag at Q1

Anchor: Q1 text (lines 110–112), unique:

```
1. **One-sentence problem statement.** "Right now, X happens / does
   not happen, and that costs Y." If the user can't write this in one
   sentence, the work is too vague — push back.
```

Append one sentence: if the one-sentence problem already smells
single-workflow / 1–3 day, say so NOW (provisional flag), with Q6
(lines 162–165) kept as the binding check. Do not move Q6.

### F4 — Stage 0.5 conversation-supplied-answers inventory

Land **between** Stage 0's closing paragraph (lines 91–93, "If the
plan exists with `status` other than `draft` or `scoped`, abort…")
and the Stage 1 heading. Anchor on the unique:

```
### Stage 1 — Read priors
```

Insert `### Stage 0.5 — Inventory conversation-supplied answers`
before it: scan the invoking conversation for material already
answering Q1–Q5; present inferred answers for confirmation (marked
as inferred); ask only the genuinely open questions in Stage 2. Stage
2's "do not invent answers" line (111) stays — Stage 0.5 makes
inference *flagged*, not silent. (Stage 2's opening sentence may need
a cross-reference: "Pose the user the following questions in order"
→ "…skipping any confirmed in Stage 0.5.")

### F6 — one line naming the 2–3 most binding priors

Anchor: the exact Stage 1 sentence (lines 105–107):

```
Read `.claude/docs/canonical-patterns.md` and
`.claude/docs/architectural-smells.md` end-to-end. These are the law-as-
stated; scope must respect them.
```

Append the requirement: after the read, emit one line naming the 2–3
priors (decision ids / pattern anchors / smell names) most binding on
this scope — un-fakeable without the read, doubles as frame
activation, and is naturally consumed by Stage 3's checklist and the
§1 Prior-constraints rows (making it load-bearing per F5's rule).

---

## 3. Script contract — scripts/plans.py

CLI (verified by reading `main()`, lines 354–396):

- Global flags: `--plans-dir`, `--specs-dir`, `--decisions-dir`
  (defaults: `ai-docs/plans|specs|decisions`).
- `init <slug> [--title] [--date] [--motivating-decision] [--force]`
  — scaffolds frontmatter (status: draft) + §1–7 placeholder body;
  exit 0 success, 2 on bad slug / existing file without `--force` /
  bad ADR id. Missing ADR for `--motivating-decision` is only a
  warning.
- `list [--json]`, `show <slug>` — exit 0; show exits 1 if not found.
- `promote <slug> --code-roots R [--spec-id] [--allow-missing]
  [--force]` — not used by this skill (that's /plan-spec).
- `audit [--json]` — exit 0 clean, 1 if any drift diagnostics,
  2 usage error. Checks ONLY: valid status enum; promoted ⇒
  successor_spec set + spec file exists; motivating_decision ⇒ ADR
  file exists. Frontmatter parse failures are stderr warnings + skip,
  NOT drift (load_plans lines 76–80). Audit is registry-wide, not
  per-plan.

Mechanizability of an artifact-truth check, factually:

- **Mechanizable in plans.py audit:** placeholder-residue detection.
  The scaffold body embeds known sentinel text ("_Filled by
  `/scope-feature`…_", lines 132–137 of plans.py); a `status: scoped`
  plan whose §1/§2 still contain that sentinel (or contain zero
  bullets) is mechanically detectable drift. Also detectable: §1
  missing the In scope / Out of scope / Non-goals / Prior constraints
  subheads; §2 with <3 bullets. These are existence/format checks.
- **NOT mechanizable; must stay a prose gate:** the F1 contract
  property itself — whether §1 prose adjudicates a hypothetical
  borderline change unambiguously. That requires generating candidate
  changes and judging them against prose semantics; it is an
  LLM-judgment gate, hence Stage 4.5 in SKILL.md, not a plans.py
  check. (The two are complementary: audit can catch hollow sections;
  only the prose gate catches plausible-but-vague sections.)

`scripts/decisions.py` (Stage 1 dependency): subcommands
`init/list/show/rebuild/audit/link-check`; both `audit --json` and
`list --json` exist as invoked at SKILL.md lines 100–101. No drift.

---

## 4. Pointer + artifact-drift audit

| Ref (SKILL.md line) | Target | Reality | Drift? |
|---|---|---|---|
| 88: `python3 scripts/plans.py init "${PLAN_NAME}"` | scripts/plans.py init | Exists, matches contract | No |
| 100: `python3 scripts/decisions.py audit --json` | decisions.py audit --json | Exists | No |
| 101: `python3 scripts/decisions.py list --json` | decisions.py list --json | Exists | No |
| 102 & 73: `ls .claude/docs/subsystems/` | directory | **Does not exist in this repo** — `ls` exits 1 on a fresh clone. (Populated by /map-subsystem in host projects; /impact-feature references it too.) No graceful-absence wording in Stage 1, unlike Stage 3's exploration fallback. | **Yes — minor: command fails when dir absent; needs an "absent is fine" note** |
| 105–106: `.claude/docs/canonical-patterns.md`, `.claude/docs/architectural-smells.md` | files | Both exist | No |
| 115–117: `knowledge/structure-redesign-lessons.md` | file | Exists (7.2 KB). Its own refs to `.claude/skills/_common/structural-design-principles.md` also resolve. | No |
| 144, 171: `reports/scope-feature/scan-<TS>/exploration.md` | convention | Dir exists with one real instance: `reports/scope-feature/scan-20260612/exploration.md`. But `<TS>` is **never assigned** in the skill (no `TS=$(date…)` in Stage 0; grep confirms) — dispatch (line 144) and read-back (line 171) must agree on a value the skill never pins. Real instance uses date-only (`20260612`), not a timestamp. | **Yes — minor: undefined placeholder; dispatch/read-back coordination is implicit** |
| 134–148: `Agent({... subagent_type: "Explore" ... "Write findings to reports/scope-feature/scan-<TS>/exploration.md" ...})` | Explore agent | **Contradiction (F8 class).** In this harness `Explore` is the read-only search agent: tools are "All tools except Agent, ExitPlanMode, Edit, Write, NotebookEdit" — the Write and Edit tools are unavailable. The dispatch prompt orders the agent to write a file. Same unexecutable-dispatch class as the F8 dogfood finding in the other skill's review: a read-only agent type asked to produce a file artifact. (Caveats: Explore retains Bash, so a shell-redirect write is *possible* but violates the agent's read-only contract and is harness-dependent; the harness explicitly returns the agent's final message to the orchestrator, which is the contract-clean channel. The one existing exploration.md proves some past run produced the file — by what mechanism is unrecorded.) Stage 3 (lines 173–177) already has a graceful fallback if the file is absent, which in a strict harness would fire **every time**, silently degrading the skill to "background exploration unavailable" on all runs. | **Yes — NEW DEFECT (F7-local): unexecutable write order to a read-only agent type. Fix direction: consume the Agent return message (run_in_background completion) or have the orchestrator write the file from the returned text, or switch agent type — adjudicate in repair, not here.** |
| 192: `/decide --supersede` | decide skill flag | Exists (`--supersede <id> --slug <new-slug>` in decide frontmatter, line 4) | No |
| 249–252: `/impact-feature`, `/plan-feature` handoffs | skills | Both exist | No |
| 235: `python3 scripts/plans.py audit` | audit | Exists; weakness documented in §3 | No (behavioral gap is F1, not drift) |

Stated runtime claim (line 70–71): "Python: `python3` (stdlib-only)" —
plans.py imports `_lib.yaml_frontmatter`, which per CLAUDE.md is
**PyYAML-backed** (requirements.txt), and decisions.py shares `_lib`.
The "stdlib-only" claim is inaccurate for the scripts the skill
invokes; venv guidance ("use `.venv/bin/python`") is also absent from
both bash blocks. **Drift — minor but real: a fresh clone without
`/engineer-init` fails Stage 0 with ModuleNotFoundError while the
skill text says stdlib-only.**

---

## 5. Load-bearing audit (every mandated verification/reporting step)

| Step (line) | Output | Consumed by | Verdict |
|---|---|---|---|
| Stage 0 status guard (91–93) | abort/proceed decision | gates whole pipeline | Load-bearing |
| Stage 1 `decisions.py audit --json` + `list --json` (100–101) | decision inventory | Stage 3 ADR check (180–182); §1 Prior constraints (218) | Load-bearing destination exists, but **nothing proves consumption** — no required artifact links the command output to §1 rows (F6-adjacent) |
| Stage 1 `ls .claude/docs/subsystems/` (102) | subsystem file list | **Nothing.** No later stage references it; full reads are deferred to /impact-feature (line 73). | **Ceremony as written** — output feeds no stage, no gate, no reply line. Either delete or give it a consumer (e.g. Stage 0.5/Q2 prompt seeding). F5 rule applies. |
| Stage 1 end-to-end read (105–107) | (none — no artifact) | Implicitly Stage 3 + §1 | **Hallucination-invited** (F6). Fix: binding-priors line, consumed by Stage 3. |
| Stage 2 Explore dispatch (134–148) | exploration.md | Stage 3 (lines 168–177) reads and incorporates; absence is noted in §1 | Load-bearing by design — but currently **unexecutable as specified** (see §4); in a strict harness the fallback fires always, making the dispatch de-facto ceremony |
| Stage 3 conflict surfacing (190–194) | user decision | gates Stage 4 | Load-bearing |
| Stage 5 `plans.py audit` (235) + "Confirm the plan loads cleanly" (238) | exit code | **Nothing downstream.** Stage 6's ≤8-line report (242–252) does not include the audit result; no gate consumes it; and per §3 it cannot even detect a parse failure of this plan (warning-and-skip) or any §1/§2 hollowness. | **Near-ceremony** (F5 risk: will be skipped). Smallest fix: make Stage 6 report it ("audit: OK / drift: N") and/or strengthen what audit checks (placeholder residue, §3). |
| Stage 6 summary (240–252) | ≤8-line reply | user + next-command routing | Load-bearing (reply contract) |

Additional note for the Stage 4.5 insertion: its output (3 borderline
adjudications) should be consumed — either echoed in the Stage 6
report (one line: "borderline gate: 3/3 adjudicated") or recorded in
the plan; otherwise the new gate is itself F5-ceremony on day one.

---

## 6. What the skill verifiably gets right (calibration honesty)

The review's positives check out against the text: Stage 1 priors-
before-conversation (95–107); Stage 2 background survey launched at
the earliest moment the target is known (126–150) with explicit
don't-wait (150) and a graceful-absence fallback (173–177); Core
beliefs as frame preamble (48–65); the sideways table re-anchoring at
drift points (262–271). The repair should preserve all four.
