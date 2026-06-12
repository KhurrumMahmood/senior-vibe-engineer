---
name: repair-skill
description: Repair an existing skill whose text cannot be blind-trusted at execution time. Runs the validated five-role loop — frame review, claim-verifying scout, change spec with declared verdict, no-invention implementer, independent verifier — plus scaled A/B lift probes and (for execution-heavy skills) a real-host dogfood. Use when a frame review, dogfood, or production incident shows a skill producing wrong execution despite plausible text.
argument-hint: "<skill-name>  (an existing .claude/skills/<name>)"
allowed-tools: Bash, Read, Grep, Glob, Write, Edit, Agent
user-invocable: true
tier: cross-cutting
job: meta
best_for: |
  Repairing, fixing, or materially revising an existing skill — a
  SKILL.md whose text misleads or under-constrains real executors,
  shown by a frame review, dogfood log, incident, or adherence
  telemetry. The standard repair gate for skill revisions arriving
  from any source, including skills imported from other projects.
not_for: |
  Authoring a new skill (use /plan-skill). Tiny wording fixes — edit
  directly and run skill_meta.py lint. Cross-skill invariant audits
  (use /check-ecosystem-consistency). Repairing scripts with no skill
  attached (normal bug-fix loop).
escalate_to: |
  /plan-skill when the repair reveals the skill should be redesigned or
  split; /decide when a repair establishes durable doctrine;
  /prevent-regression when a repaired contract deserves a lint/test.
language: any
framework: any
lanes: [skill-development, quality-kernel]
stage: refactor
entrypoint: true
consumes: [frame_review, dogfood_log, skill_context]
produces: [repaired_skill, campaign_record, lift_report]
evidence_required: [scout_verification, change_spec, independent_verification, lift_result]
risk_triggers: [skill_rewrite, doctrine_surface, weak_tier_executors]
max_overhead: "Stop if no evidence of execution-time failure exists — review first, repair second."
---

# /repair-skill

You are the **orchestrator** of a skill repair. You author the change
spec and judge the results; fresh sub-agents do the reading-heavy and
conflict-of-interest-prone roles. The deliverable is the repaired
skill (committed per logical unit) plus a campaign record under
`.claude/tasks/skill-repairs/<skill>/` that doubles as the repair's
replay case: what failed, what changed, what a future run must pass.

## How success is judged

- The **independent verifier** (Stage 5) passes every finding as
  RESOLVED with a clean no-invention audit — it shares no context
  with the implementer and is told to refute, not confirm.
- The **lift probe** (Stage 6) moves the headline defect site at the
  weakest supported tier, with zero regressions, against criteria
  locked before any probe returns.
- For execution-heavy skills, a **real-host dogfood** (Stage 7)
  completes from the text alone, without forced improvisation.
- Every residual is fixed or ledgered — never silently dropped.
Write toward these gates from Stage 0.

## Core beliefs

1. **Three failure surfaces, three instruments — none substitutes.**
   The verifier checks internal consistency; probes check behavior at
   known defect sites; only execution against a host the skill was
   not written on exposes the unexecutable-against-reality class.
   Verifier PASS is not done.
2. **Reviews are compressions; verify before acting.** A review's
   claims can themselves be distorted (a "missing file" that exists
   with different content). The scout re-derives every claim from
   ground truth before the spec is written.
3. **Nothing invented.** Where source fragments are insufficient, the
   repair writes an explicit `<!-- host-adapter: ... -->` slot, never
   plausible filler. The verifier diffs for this.
4. **The text must carry what the executor cannot reconstruct,
   in the phase where it is consumed.** Lift concentrates where
   content was absent and is largest at the weakest tier; mandates
   diffused in a knowledge corpus do not reach weak executors.
5. **Score grounding, not just behavior.** An old-condition probe can
   produce right-looking behavior while citing mandates that do not
   exist. A right answer with an invented citation is a latent
   failure; the repair's value at such sites is that the citation
   becomes real.

## Pipeline

### Stage 0 — Intake and scale

Confirm the target exists and evidence of execution-time failure
exists (frame review, dogfood log, incident, telemetry). No evidence →
run Stage 1 as a standalone review and stop for triage.

Freeze the pre-repair skill: `mkdir -p /tmp/skill-repairs-old && cp -R
.claude/skills/<skill> /tmp/skill-repairs-old/<skill>` (probes need
the old condition). Create `.claude/tasks/skill-repairs/<skill>/`.

Scale gate — pick and state one:
- **Full loop** (doctrine-bearing: other skills or docs cite it as
  authority; execution-heavy: it edits code/files or orchestrates
  multi-phase runs; or ≥3 high-severity findings): all stages
  including dogfood.
- **Light loop** (small prose-only skills, ≤2 findings): Stages 1–5
  plus one probe cell; state what was skipped and why.

### Stage 1 — Frame review (skip only if a review exists AND the
skill is unchanged since — check `git log` against the review date)

Dispatch a fresh sub-agent (`general-purpose`) with
`knowledge/frame-review-rubric.md`, the skill's full file list, and
the *paths* of its scripts with the instruction to derive their
contracts itself (`--help`, argparse source). The Stage 2 scout
re-derives them independently — two derivations is the point, not
duplication. Output:
`.claude/tasks/skill-repairs/<skill>/frame-review.md` — findings F1…Fn
with stage/line citations, execution-failure naming, smallest fixes,
and what the skill gets right.

### Stage 2 — Scout

Dispatch a fresh sub-agent to write
`.claude/tasks/skill-repairs/<skill>/scout.md`:

1. **Claim verification** — each finding marked TRUE / PARTLY (with
   correction) / FALSE against quoted ground truth.
2. **Edit anchors** — exact lines + surrounding quotes per fix.
3. **Script contracts** — CLI surface, exit codes, output shapes of
   every script the skill calls (fixes must match executable reality).
4. **Pointer + artifact-drift audit** — every referenced file, flag,
   and artifact vs. the filesystem. This is where new defects hide.
5. **Load-bearing audit** — every mandated step and its consumer.

### Stage 3 — Change spec (orchestrator-authored)

Write `change-spec.md`: one C-item per finding plus scout-found
defects, each with its smallest responsible fix; a **declared-verdict
block** at the top stating how the verifier will judge; constraints
(no renumbering, preserve voice, nothing invented, gaps become
host-adapter slots); an explicit OUT-OF-SCOPE list routing anything
deferred to the ledger. Drop findings the scout marked FALSE; fold in
its corrections.

### Stage 4 — Implement

Dispatch a fresh sub-agent with the spec + scout (not the session):
smallest edits, anchored by the scout's quotes, judgment calls
recorded in `implementation.md`. Script changes require tests, run
green, plus any skill-local validate command — discovered by grepping
the target's SKILL.md and scripts for `--validate`/test invocations;
"none found" is recorded explicitly in `implementation.md` so absence
is distinguishable from a missed check. The implementer does not
commit.

### Stage 5 — Independent verification

Dispatch a fresh, non-context-sharing sub-agent told to **refute**:
per C-item RESOLVED / PARTIAL / UNRESOLVED with quotes; a
no-invention diff audit (every added sentence traces to spec, scout
fragments, or pre-existing text); a new-defect sweep of the same
classes; live re-runs of any script checks. Output:
`verification.md` with overall PASS/FAIL. FAIL → fix via Stage 4 and
re-verify the failed items; do not argue with the verifier in prose.

### Stage 6 — Lift probes

Lock criteria FIRST in `lift-protocol.md` (or the shared one in
`.claude/tasks/skill-repairs/`): per probe site, the score scale and
the old/new predictions. Default scale: one probe at the headline
defect site, weakest supported tier (haiku), old vs new.

The harness, exactly: each probe is one fresh sub-agent (model set to
the probe tier) whose prompt contains (a) a scenario placing it
mid-execution at the defect site, (b) the instruction to read the
skill at ONE path — the frozen `/tmp/skill-repairs-old/<skill>` copy
for the old condition, the working tree for the new — and follow it
exactly, (c) the declared-verdict sentence: "your output will be
judged on whether it matches what the skill actually mandates."
Blind means: no mention of a repair, a diff, or the other condition.
Save each agent's full reply verbatim as
`lift-probes/{old,new}-<P>.md` — the transcript IS the judging input;
judge only from transcripts, never from memory of them. Judge into
`lift-report.md`, scoring **grounding as well as behavior** (do cited
mandates exist in the text the agent read?). A regression at any site
blocks close-out until explained or fixed.

### Stage 7 — Real-host dogfood (full loop; execution-heavy skills)

Run the repaired skill's heaviest phase on a codebase it was not
written on. Acquisition: clone any real repo the operator can name
(a private host project is fine — the run stays local) into /tmp at
a representative messy commit (`git clone <src> /tmp/<name> && git -C
/tmp/<name> checkout <commit>`); never run against the origin
working tree. If no foreign repo is available, say so and substitute
live script probes — never simulate a dogfood. Conditions stay
hostile-but-realistic (no convention docs, no venv, detached HEAD,
commits forbidden). The executor logs
every friction citing the text it followed, and answers: **could a
fresh executor complete this from the text alone?** Frictions become
a same-day round-2 spec (back through Stages 3–5, scaled to the
edits). Script-backed but conversation-shaped skills substitute live
script probes. Keep the dogfood log in the campaign record — it is
the replay case.

### Stage 8 — Close out

- **Class-lift gate.** For each repaired defect, name its class in
  one sentence, define the cheapest detector (usually a grep), and
  RUN it across the skill catalog. The detector's output is the
  artifact — paste hit counts in the reply. Siblings found → batch
  them (one sweep spec, not N future bug reports); class
  mechanizable → route to /prevent-regression. A defect fixed only
  where it was reported is a recurring tax.
- Residual triage: each verifier/probe/dogfood residual is fixed
  (small, in-class) or ledgered with its routing named — never
  dropped.
- Ledger: a note event on the target skill's idea entry (or
  `repair-skill`'s) with the campaign result; lessons for anything
  that generalizes. Mechanism: `/track-idea` (`python3
  .claude/skills/track-idea/scripts/track.py event|lesson ...`)
  writing `.claude/ideas/log.jsonl` — NOT `scripts/ledger.py`, which
  is the refactor file-review ledger, a false friend.
- Scrub absolute/identity paths from the campaign record (it is
  tracked); commit the skill repair and the campaign record as
  separate logical units.
- Reply contract: verifier verdict, lift table, dogfood verdict (or
  "not run — light loop"), residuals and where each went.

## When things go sideways

| Symptom | Action |
|---|---|
| No evidence of execution failure | Stage 1 standalone review, then stop for triage — repair needs a defect spec |
| Review claim contradicts ground truth | Trust the scout's quoted reality; fold the correction into the spec (reviews distort) |
| Implementer cannot apply a fix without inventing content | Host-adapter slot + note in implementation.md; never filler |
| Verifier FAILs items | Stage 4 on the failed items only; re-verify; no prose appeals |
| Probe shows a regression | Block close-out; diagnose whether the spec or the implementation caused it |
| Old-condition probe scores well | Check grounding — fabricated citations mean the score is inflated, not that repair is unneeded |
| Dogfood frictions exceed the review's findings | Expected — different instrument, different class; round-2 spec, same day |
| Repair keeps growing past the spec | Stop; the skill needs /plan-skill redesign, not more patches |

## Repository layout

```
.claude/skills/repair-skill/
├── SKILL.md                        # this file — orchestrator
└── knowledge/
    └── frame-review-rubric.md      # six review lenses + the two
                                    # execution-time defect classes
```

Exemplar campaigns (worked examples, not dependencies):
`.claude/tasks/refactor-subsystem-repair/` (full loop, incl. dogfood
round-2) and `.claude/tasks/skill-repairs/` (scaled batch of three).
