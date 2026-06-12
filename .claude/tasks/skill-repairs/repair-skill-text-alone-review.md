# Adversarial review — /repair-skill, text-alone executability

Reviewer condition: no context from the session that produced the skill.
Inputs read: `.claude/skills/repair-skill/SKILL.md`,
`.claude/skills/repair-skill/knowledge/frame-review-rubric.md`, plus
filesystem/CLI checks of every artifact the text references. No edits made
anywhere except this file.

Question: **could a fresh executor run the full loop from the text alone?**

Verdict up front: **NO for the full loop, YES for Stages 0–5 and 8.**
Stages 0–5 and 8 are executable from the text with only minor improvisation;
Stage 6 (lift probes) and Stage 7 (real-host dogfood) under-specify the
probe harness and the host-acquisition procedure enough that a fresh
executor must improvise the parts that make the measurement valid.

---

## Stage-by-stage walk (what I would literally do, and where I'd improvise)

### Stage 0 — Intake and scale

Would do: confirm `.claude/skills/<skill>/` exists; look for a frame
review / dogfood log / incident as evidence; `cp -R` the skill to
`/tmp/skill-repairs-old/<skill>`; `mkdir -p .claude/tasks/skill-repairs/<skill>/`;
declare full vs light loop.

- Executable. The evidence gate is clear, the no-evidence fallback
  (Stage 1 standalone, then stop) is explicit, and the scale-gate
  criteria are concrete (doctrine-bearing / execution-heavy / ≥3
  high-severity vs prose-only ≤2 findings).
- [minor] The `cp -R` command fails if `/tmp/skill-repairs-old/` does
  not exist yet — no `mkdir -p` is given. Trivially recoverable.
- [minor] "Doctrine-bearing" and "execution-heavy" are undefined terms.
  Guessable from context (Stage 7's parenthetical), but a borderline
  skill forces a judgment call with no criteria.

### Stage 1 — Frame review

Would do: spawn a `general-purpose` sub-agent carrying the rubric file,
the skill's file list, and "its script contracts"; receive
`frame-review.md` with F1…Fn findings.

- Mostly executable: agent type is named, rubric file exists, output
  path and finding format (stage/line citations, execution-failure
  naming, smallest fixes, what's right) are specified, and the rubric
  itself tells the reviewer exactly what to answer.
- [would-stall] **"its script contracts" is an input I do not have a
  procedure to produce.** Script contracts (CLI surface, exit codes,
  output shapes) are *derived in Stage 2 by the scout* — but Stage 1
  consumes them first. Chicken-and-egg: do I run `--help` on every
  script myself? Paste source? Hand the reviewer paths and tell it to
  derive them? Three defensible readings, none chosen by the text.
- [minor] "skip if a current one exists" — no staleness criterion. A
  three-week-old review of a since-edited skill: current or not?

### Stage 2 — Scout

Would do: spawn a fresh sub-agent to write `scout.md` with the five
numbered sections.

- Executable and well-specified — the five sections are concrete,
  TRUE/PARTLY/FALSE with quoted ground truth is checkable, and "fixes
  must match executable reality" gives the scout a clear bar.
- [minor] No agent type named (Stage 1 names `general-purpose`; here
  just "a fresh sub-agent"). Default is fine, but inconsistent.

### Stage 3 — Change spec

Would do: author `change-spec.md` myself with C-items, a
declared-verdict block, the four constraints, an OUT-OF-SCOPE list.

- Executable. The constraint list (no renumbering, preserve voice,
  nothing invented, gaps → host-adapter slots) is exactly the kind of
  content an executor cannot reconstruct; it is in the phase where it
  is consumed. Drop-FALSE / fold-corrections is unambiguous.
- [minor] Output path is implied (`change-spec.md`, presumably in the
  campaign dir) but, unlike Stages 1–2, not written as a full path.
  Same applies to `implementation.md`, `verification.md`,
  `lift-report.md`. Recoverable from the Stage 0 dir creation + the
  exemplar campaigns, which all use the campaign dir.

### Stage 4 — Implement

Would do: spawn a fresh sub-agent with spec + scout only; smallest
anchored edits; judgment calls into `implementation.md`; tests for any
script change; no commit.

- Executable. "with the spec + scout (not the session)" is the right
  contamination control, and the no-commit rule prevents the classic
  sub-agent overreach.
- [would-stall] **"plus any skill-local validate command" — undefined.**
  Nothing tells me how to discover whether the target skill has one
  (a `scripts/validate*`? a frontmatter field? `skill_meta.py lint`?).
  I would improvise a search and might miss the real one or run the
  wrong thing and treat its absence as a pass.

### Stage 5 — Independent verification

Would do: spawn a fresh non-context-sharing sub-agent told to refute;
per-C-item RESOLVED/PARTIAL/UNRESOLVED with quotes; no-invention diff
audit; new-defect sweep; live script re-runs; PASS/FAIL into
`verification.md`. FAIL → Stage 4 on failed items, re-verify.

- Executable. The refute framing, the no-invention audit definition
  ("every added sentence traces to spec, scout fragments, or
  pre-existing text"), and the "do not argue with the verifier in
  prose" back-edge are all precise.
- [minor] The Stage 4↔5 fix/re-verify cycle has no iteration cap. The
  sideways table's "repair keeps growing past the spec → /plan-skill"
  is a partial stop condition, but "growing past the spec" and "stuck
  re-failing the same item" are different failure shapes.

### Stage 6 — Lift probes

Would do: write `lift-protocol.md` with per-site score scale and
old/new predictions, locked before any probe returns; run one probe at
the headline defect site on `model: haiku`, old (frozen `/tmp` copy)
vs new (working tree), fresh blind agents; judge into `lift-report.md`
scoring behavior and grounding.

- [would-corrupt] **The probe harness itself is unspecified, and no
  probe artifact is demanded.** The text never says how to construct a
  probe: what the haiku agent is given (the SKILL.md text? a scenario
  prompt placing it mid-stage? both?), how the old condition is
  delivered (point it at the frozen copy — but with what framing so it
  doesn't read the working tree?), what "blind" concretely excludes,
  or how many probes constitute a cell. A fresh executor will
  improvise a harness, and a badly improvised harness produces a
  *plausible-looking but invalid* lift table — the exact
  "right-looking behavior" failure the skill's own Core belief 5
  warns about. Compounding it: Stage 6 demands no transcript artifact.
  The exemplar campaign saves per-probe transcripts
  (`refactor-subsystem-repair/lift-probes/old-haiku-P1.md` etc.), so
  the practice exists — but the SKILL.md text does not mandate it,
  which is precisely the rubric's HALLUCINATION-INVITED shape: "run
  probes" can be satisfied by assertion. The mitigation the text does
  provide (criteria locked first, predictions declared) is real but
  does not constrain harness construction.
- [would-stall] The only way to learn how probes are actually built is
  the exemplar `lift-protocol.md` / `lift-probes/` — which the text
  explicitly labels "worked examples, not dependencies." In this repo
  they exist and rescue the stage; on any host where the skill is
  imported without `.claude/tasks/`, Stage 6 is not reconstructible
  from the text. The exemplars are load-bearing while being declared
  optional.
- [minor] "`lift-protocol.md` (or the shared one in
  `.claude/tasks/skill-repairs/`)" — the shared file is the locked
  protocol of three *past* repairs, not a template; "or the shared
  one" reads as "you may reuse it," which would be wrong. Ambiguous.
- [minor] Stage 6 judging is done by the orchestrator, who also wrote
  the spec and the predictions — the one role the skill does *not*
  hand to a conflict-free agent. Locked criteria mitigate; still a
  same-party-judge exception to the skill's own design principle,
  worth a sentence of justification in the text.

### Stage 7 — Real-host dogfood

Would do: find "a codebase the skill was not written on"; arrange
no convention docs / no venv / detached HEAD / commits forbidden; run
the repaired skill's heaviest phase; log frictions citing followed
text; answer the text-alone question; round-2 spec same day.

- [would-stall] **No procedure for acquiring or selecting the host.**
  Which codebase? A sibling project on disk? A public repo to clone?
  What qualifies as "was not written on" (this repo's own scripts?
  another of the user's projects?)? What size/shape makes the dogfood
  representative? The hostile-conditions list is good and concrete,
  but the precondition — a suitable foreign host — is an input the
  text assumes I have. A fresh executor stalls here or picks a
  degenerate host (e.g., a toy directory) that makes the dogfood
  vacuously pass.
- [minor] "Script-backed but conversation-shaped skills substitute
  live script probes" — both the category and the substitution are
  one clause each; I could not confidently classify a borderline
  skill or design the substitute from this sentence.

### Stage 8 — Close out

Would do: per repaired defect, name the class, define a grep detector,
run it across `.claude/skills/`, paste hit counts; triage residuals
(fix or ledger with routing); ledger note event; scrub absolute paths;
two separate commits; reply contract.

- Largely executable, and the class-lift gate is the best-specified
  judgment step in the file ("the detector's output is the artifact —
  paste hit counts in the reply" is exactly the anti-hallucination
  fix shape the rubric prescribes).
- [would-stall] **"Ledger: a note event on the target skill's idea
  entry" names no mechanism, and the obvious candidate is wrong.**
  `scripts/ledger.py` exists and is called "ledger" — but it is the
  *file-review* ledger (architecture drift tracking), not the idea
  ledger. The actual surface is `.claude/ideas/log.jsonl` via
  `/track-idea`, which this skill never mentions. A fresh executor
  who greps `scripts/` for "ledger" lands on the wrong CLI and
  writes a bogus file-review entry; one who reads CLAUDE.md's
  capture-tiers section can recover. Naming `/track-idea` (or the
  log path) in the text is a one-line fix.
- [minor] "lessons for anything that generalizes" — which of the five
  capture tiers? Resolvable via CLAUDE.md, not via this text.

---

## The skill's own rubric, applied to itself

**GOAL** — Strong. The deliverable (repaired skill) is tested for
artifact truth three independent ways (refute-mode verifier, locked-
criteria probes, foreign-host dogfood), and Core belief 1 explicitly
names the "verifier PASS is not done" trap. One gap: Stage 6's lift
verdict is produced by the spec author with no artifact (transcripts)
that lets anyone re-derive it — the headline success number is the
least independently checkable output in the pipeline.

**FRAME** — Good. "How success is judged" sits at the top *and* ends
with "Write toward these gates from Stage 0"; the sideways table
re-activates the key rules (trust the scout, no prose appeals, block
on regression) at the moments they're needed. The no-invention frame
is re-stated inside Stages 3, 4, and 5 — in-phase, not preamble-only.

**SURVEY** — Adequate. Stage 2 is a real mandated inventory with
defined sections, and Stage 0 gates on evidence existing. The rubric's
phase-0-over-conversation-context question is half-answered: the skill
quarantines session context *downstream* (implementer gets spec+scout
only) but never tells the orchestrator to inventory what the invoking
conversation already established (e.g., an in-session frame review's
known distortions) beyond "skip Stage 1 if current."

**WORKFLOW TRAPS** — Mostly handled. Back-edges exist for verifier
FAIL, probe regression, dogfood frictions, dead-end evidence, and
scope creep (→ /plan-skill). Two residual traps: the Stage 4↔5 loop is
uncapped, and Stage 6/7's most expensive work (probe harness design,
host acquisition) is encountered *after* Stages 1–5's sunk cost, with
no early check that a suitable host or harness exists — the exact
"ordering that fights incentives" shape the rubric names.

**LOAD-BEARING TEST** — Good wiring overall. frame-review → scout
(claim verification) → spec → implementer → verifier → reply; dogfood
log → round-2 spec; detector output → pasted counts in reply. Two
weakly-consumed artifacts: `implementation.md` judgment calls (no
stage is told to read them — the verifier audits the *diff*, not the
judgment log) and the frozen `/tmp` copy after Stage 6 (never cleaned
up or referenced again).

**HALLUCINATION-INVITED** — One real instance: Stage 6 "fresh blind
agents… Judge into lift-report.md" demands no output that could not be
produced without running probes (no transcript, no agent-id, no pasted
probe reply). Stage 8's class-lift gate, by contrast, is the model fix
("paste hit counts"). Stage 7 is safe (friction log with text
citations is the artifact).

**Artifact-reality drift (checked against this repo)** — Clean.
`knowledge/frame-review-rubric.md` exists and matches its layout-
comment description (six lenses + two classes). Both exemplar
campaign dirs exist with the promised contents (full loop incl.
dogfood-log + round-2 + lift-probes transcripts; scaled batch of
three + shared lift-protocol.md). `skill_meta.py lint` exists with
that exact subcommand. `/plan-skill`, `/decide`, `/prevent-regression`,
`/check-ecosystem-consistency` all exist. The campaign-record dir is
git-tracked, so the "scrub paths (it is tracked)" claim is true. The
one drift-adjacent hazard is the unnamed-ledger ambiguity above
(`scripts/ledger.py` is a false-friend match).

**Unexecutable contracts** — Mostly clean. `general-purpose` agents
have full tools (read+write — Stage 1/2/4/5 demands are satisfiable);
`haiku` is an available model tier for the Agent tool, so Stage 6's
"weakest supported tier (haiku)" is executable; frozen-copy reads from
`/tmp` are permitted. The two contracts that may not execute: Stage 7
presumes a foreign host codebase exists and is reachable (nothing in
the environment guarantees one), and Stage 0's `cp -R` into a
nonexistent `/tmp` parent dir fails as written.

---

## What the text gets right (honesty bar)

- **Role separation is genuinely well designed**: the spec author
  doesn't implement, the implementer doesn't see the session, the
  verifier shares no context and is told to refute, and the table
  bans prose appeals. This is the hardest part of a repair loop to
  get right and the text nails it.
- **Freeze-the-old-condition at Stage 0** is exactly the move that
  makes A/B probes possible at all; most skills would forget it until
  Stage 6 when it's too late.
- **The no-invention / host-adapter-slot doctrine** (Core belief 3,
  re-enforced in Stages 3–5 and the sideways table) is concrete,
  checkable by diff, and stated in every phase where it's consumed.
- **Locked-before-results probe criteria with declared predictions**
  is the right anti-rationalization shape, and "score grounding, not
  just behavior" (fabricated citations inflate old-condition scores)
  is a sharp, non-obvious insight stated where it's needed.
- **The class-lift gate** converts each fix into a catalog-wide sweep
  with a pasted-output artifact — the strongest single paragraph in
  the file.
- **The evidence gate** ("no evidence → review and stop") prevents the
  skill's own misuse, and `max_overhead` repeats it in frontmatter.
- **The rubric file is excellent as a standalone instrument**: six
  lenses each with the failure it catches and the fix shape, plus an
  honest statement of its own limits (the two classes it cannot reach
  and which stages exist for them).
- Frontmatter (`consumes`/`produces`/`evidence_required`) is
  consistent with the body — no promised-but-unwired evidence.

---

## Severity-ranked improvisation points

| # | Severity | Point |
|---|---|---|
| 1 | would-corrupt | Stage 6 probe harness unspecified (what the blind agent is given, how old/new conditions are delivered, what "blind" excludes) and no probe transcript demanded — an improvised harness yields a plausible-but-invalid lift table, the skill's own named failure mode |
| 2 | would-stall | Stage 7 gives no procedure for acquiring/selecting the foreign host codebase — the full loop's distinguishing stage has an assumed input |
| 3 | would-stall | Stage 8 "ledger" names no mechanism; `scripts/ledger.py` is a false-friend (file-review ledger), the real surface is `/track-idea` → `.claude/ideas/log.jsonl`, never mentioned |
| 4 | would-stall | Stage 1 consumes "script contracts" that Stage 2 produces — no procedure for the orchestrator to derive them first |
| 5 | would-stall | Stage 4 "any skill-local validate command" — no discovery procedure; absence vs missed-it are indistinguishable |
| 6 | would-stall | Stage 6 is reconstructible only via exemplar campaigns explicitly labeled "not dependencies" — load-bearing on this repo, absent on an importing host |
| 7 | minor | `cp -R` into `/tmp/skill-repairs-old/` without `mkdir -p` |
| 8 | minor | "skip if a current [frame review] exists" — no staleness criterion |
| 9 | minor | Stage 4↔5 re-verify loop uncapped |
| 10 | minor | "or the shared [lift-protocol]" reads as reusable template; it's a past campaign's locked protocol |
| 11 | minor | Stage 3–6 artifact filenames given without paths (campaign dir implied, not stated) |
| 12 | minor | Orchestrator is same-party judge of Stage 6 — defensible given locked criteria, but unjustified in text |
| 13 | minor | "doctrine-bearing"/"execution-heavy"/"conversation-shaped" classifications undefined for borderline skills |

## Verdict

**NO — not fully executable from the text alone.** Stages 0–5 and 8
are (with minor friction); Stage 6's measurement validity and Stage
7's precondition both depend on improvisation or on exemplar artifacts
the text disclaims as dependencies. The smallest repair: (a) a short
probe-construction contract in Stage 6 plus a mandated transcript
artifact, (b) a host-selection sentence in Stage 7, (c) name
`/track-idea` in Stage 8, (d) resolve the Stage 1 script-contracts
chicken-and-egg. That is four edits, not a redesign — the skeleton is
sound.

---

## Re-verification (post-fix)

Re-checked the six severity-ranked findings against the current
`.claude/skills/repair-skill/SKILL.md` (read-only pass; resolving
claims spot-checked against the filesystem: `track-idea/scripts/track.py`
exists, `scripts/ledger.py` exists as the named false friend, both
exemplar campaign dirs exist).

**Finding 1 (would-corrupt — Stage 6 probe harness unspecified): RESOLVED.**
Stage 6 now contains an in-text harness contract — "The harness,
exactly: each probe is one fresh sub-agent (model set to the probe
tier) whose prompt contains (a) a scenario placing it mid-execution at
the defect site, (b) the instruction to read the skill at ONE path —
the frozen `/tmp/skill-repairs-old/<skill>` copy for the old condition,
the working tree for the new — and follow it exactly, (c) the
declared-verdict sentence." All four sub-checks pass: prompt contents
are enumerated (a/b/c); old/new delivery is path-specific per
condition; "blind" is defined by exclusion ("Blind means: no mention
of a repair, a diff, or the other condition"); and the transcript
artifact is mandated and made the sole judging input ("Save each
agent's full reply verbatim as `lift-probes/{old,new}-<P>.md` — the
transcript IS the judging input; judge only from transcripts, never
from memory of them"). This also closes the HALLUCINATION-INVITED
shape — a lift verdict can no longer be produced by assertion.

**Finding 2 (would-stall — Stage 7 no host-acquisition procedure): RESOLVED.**
Stage 7 now gives both the procedure and the honest fallback:
"Acquisition: clone any real repo the operator can name (a private
host project is fine — the run stays local) into /tmp at a
representative messy commit … never run against the origin working
tree. If no foreign repo is available, say so and substitute live
script probes — never simulate a dogfood." The fallback is honest (say
so + substitute, not simulate), and the never-against-origin rule
prevents the degenerate-host hazard.

**Finding 3 (would-stall — Stage 8 ledger mechanism unnamed): RESOLVED.**
Stage 8 now names the correct surface and explicitly warns off the
false friend: "Mechanism: `/track-idea` (`python3
.claude/skills/track-idea/scripts/track.py event|lesson ...`) writing
`.claude/ideas/log.jsonl` — NOT `scripts/ledger.py`, which is the
refactor file-review ledger, a false friend." Both paths verified to
exist, so the disambiguation is grounded, not aspirational.

**Finding 4 (would-stall — Stage 1 script-contracts chicken-and-egg): RESOLVED.**
Stage 1 now picks one of the three readings and justifies the apparent
duplication: the sub-agent gets "the *paths* of its scripts with the
instruction to derive their contracts itself (`--help`, argparse
source). The Stage 2 scout re-derives them independently — two
derivations is the point, not duplication." The orchestrator no longer
needs an input it has no procedure to produce.

**Finding 5 (would-stall — Stage 4 validate-command discovery): RESOLVED.**
Stage 4 now specifies discovery and disambiguates absence: "any
skill-local validate command — discovered by grepping the target's
SKILL.md and scripts for `--validate`/test invocations; 'none found'
is recorded explicitly in `implementation.md` so absence is
distinguishable from a missed check."

**Finding 6 (would-stall — Stage 6 reconstructible only via exemplars): RESOLVED.**
The harness contract quoted under Finding 1 lives in the SKILL.md body
itself, in the phase where it is consumed; an importing host without
`.claude/tasks/` can now construct valid probes from the text alone.
The closing line "Exemplar campaigns (worked examples, not
dependencies)" is now true rather than aspirational. (The minor
"or the shared one in `.claude/tasks/skill-repairs/`" ambiguity —
original minor #10 — persists, but it no longer carries the stage.)

Out-of-scope observation: minors #7 (Stage 0 now reads "`mkdir -p
/tmp/skill-repairs-old && cp -R …`") and #8 (Stage 1 header now reads
"skip only if a review exists AND the skill is unchanged since — check
`git log` against the review date") were also fixed in passing.

### Revised verdict

**YES — executable from the text alone.** All six ranked findings
(1 would-corrupt + 5 would-stall) are RESOLVED in the current text;
the remaining improvisation points are the original minors (#9–#13),
none of which corrupt a measurement or stall a stage. The original
"NO for the full loop" verdict is superseded.
