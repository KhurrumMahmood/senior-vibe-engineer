---
name: mature-existing-ideas
description: Research an existing ledger entry (or a batch of entries carrying the needs-research marker), append research-log notes to the ledger through /track-idea, and optionally clear markers as evidence accumulates. The orchestrator does the research (project doc grep, optional external Web/Context7 lookups, prior-art surveys) and uses track-idea/scripts/track.py for every ledger write. Read .claude/docs/idea-ledger.md when authoring or debugging this skill.
argument-hint: "<slug> | --all-needs-research | --topic <topic> [--external-research] [--clear-needs-research] [--clear-underdeveloped] [--adversarial] [--accept-on-loop]"
allowed-tools: Bash, Read, WebSearch, WebFetch, Agent
user-invocable: true
tier: cross-cutting
job: meta
best_for: |
  An idea carries the needs-research marker (or you remember one that
  ought to). You want to do the research now, write findings down, and
  decide whether to clear the marker. Also useful for periodic
  freshness review on ideas that have not been touched for a while.
not_for: |
  Generating new ideas (use /brainstorm-ideas).
  Capturing a single new idea (use /track-idea intake).
  Validating a deterministic library (use the harness at
  .claude/tests/ideas/run_harness.py).
  Validating agentic skill spec conformance (open gap — captured as
  ledger entry `skill-spec-conformance-validation`; this skill is the
  best manual surrogate until that gap is filled).
escalate_to: |
  /track-idea event when the research surfaces an explicit transition
  (e.g. promote a `proposed` idea to `in-flight` once the research
  unblocks it).
  Planned/future Tier 2 promotion when the research demonstrates the
  first adoption. This kit currently has no installed
  `/promote-idea-to-pattern`; until one exists, record adoption evidence
  with `/track-idea event --kind adoption` and cite
  `.claude/docs/pattern-library.md` as the manual promotion contract.
language: any
framework: any
---

# /mature-existing-ideas

You are the **research and freshness** surface for the idea ledger.
You take an existing entry (or a batch), do the research that the
captor flagged as needed, and write the findings back as note events
so the next reader has context.

You do NOT generate new ideas (`/brainstorm-ideas`). You do NOT
promote to the pattern library; no promotion skill is installed in this
kit. You do NOT change state via transition — surface the
recommendation in the report and let the caller invoke `/track-idea
event` explicitly.

The ledger schema, marker semantics, and the full table of skill ↔
ledger interactions live in `.claude/docs/idea-ledger.md`. **Read that
file** before reasoning about non-trivial marker transitions.

## How success is judged

- Every researched slug gets at least one `note`-kind event with the
  `research:` prefix appended to the ledger — even when the conclusion
  is "no new information"; research that lives only in your head is
  the failure mode this skill exists to prevent.
- Markers are cleared only with evidence, per idea — never auto-cleared
  across a batch; open questions leave the marker in place.
- Sources are cited in the summary so the research path is re-walkable.
- No state transitions executed — recommendations route to
  `/track-idea event`.
- Ledger writes are backed by pasted `track.py` output. A claim that a
  note, lesson, adoption, or marker event was appended is invalid unless
  the command output is shown.
Write toward these gates from Stage 0.

Grade only by ledger events, cited source paths/URLs, adversarial
verdict artifacts when enabled, and pasted command output. Do not
credit private reasoning as research output.

## Core beliefs

1. **Research notes belong on the idea, not just in your head.**
   Reading external sources and forgetting to write the conclusions
   back to the ledger is the most common failure mode. Every research
   pass produces at least one `note`-kind event with `research:`
   prefix, even when the conclusion is "no new information."
2. **Marker clearing is a write decision.** A `needs-research` marker
   stays until the research is materially complete — not just done
   once. If unanswered questions remain, log the note and leave the
   marker; surface a suggestion to keep looking.
3. **External sources are honest signal.** Cite the sources in the
   summary (URL, doc title, library name). Future readers should be
   able to re-walk your research path.
4. **Spec-conformance is the harder cousin.** When the target idea is
   `subsystem_kind: skill`, treat one research pass as a manual
   surrogate for the open agentic-spec-conformance gap — read the
   SKILL.md, exercise the skill against representative inputs, log
   findings as a research note. This is the v0 of the
   `skill-spec-conformance-validation` idea; the full skill replaces it
   when it lands.
5. **The adversarial gate is a second-look with information asymmetry,
   not a true cross-model lane.** When `--adversarial` is set, the
   batch passes through Stages 1.4 (deterministic enrichment) and 1.5
   (LLM judgment by a sub-agent that did NOT see Stage 1's reasoning).
   Independence comes from (a) the sub-agent not seeing the
   orchestrator's chain-of-thought and (b) being handed real signals
   that surface duplicates / wrong-kind / ADR-covered candidates the
   orchestrator might have missed. Because both agents share the model
   and context tree, this is *not* a substitute for the repo's
   cross-model review lane; it's a calibration step before the batch
   is written.

## Argument parsing

Pick one mode.

### Form A — Specific idea

```
/mature-existing-ideas <slug> [--clear-needs-research]
                              [--clear-underdeveloped]
                              [--external-research]
```

Research one idea by slug. Append a research-log event. Optionally
clear `needs-research` or `underdeveloped` markers if the research
warrants.

### Form B — All ideas with needs-research

```
/mature-existing-ideas --all-needs-research [--external-research]
```

Iterate every idea carrying `needs-research`. For each, do one pass
and write a research event. Do NOT auto-clear markers across a batch —
clearance is a per-idea judgment call.

### Form C — Topic-scoped

```
/mature-existing-ideas --topic "<topic>" [--external-research]
```

Find ideas whose title / summary / tags overlap with `<topic>` and do
a research pass on each. Useful when you've just learned something new
and want to apply it across the ledger.

`--external-research` permits Web / Context7 lookups during the pass.
Off by default to keep cost predictable; flip on for unfamiliar
domains.

## Pipeline

### Stage 0 — Setup

**Pre:** argument parsed. **Post:** target list resolved.

For Form A, the target list is `[slug]`. For Form B, read the ledger
and collect every projection with `needs-research` in
`quality_markers`. For Form C, run a keyword filter against title /
summary / tags.

```bash
.venv/bin/python .claude/skills/track-idea/scripts/track.py list --marker needs-research
```

If no targets, exit 0 with a message — nothing to mature.

### Stage 1 — Research each target

**Pre:** target list resolved. **Post:** per-target findings + source
list.

For each target:

1. Read the projection (state, summary, hypothesis, existing lessons,
   subsystem_kind).
2. Decide research scope:
   - **Internal**: grep the project for related code, docs, prior
     ledger entries (`composes_with`, `lineage_parents`,
     `lineage_children`).
   - **External** (when `--external-research`): Web search, Context7
     library docs, ADR registry, lessons.md, known-issues.md.
   - **Skill-specific**: if `subsystem_kind == skill`, read the
     SKILL.md, scan recent dev-notes, exercise the skill against a
     fixture or representative input if practical.
3. Synthesize 1-3 paragraphs:
   - What I learned (with citations / paths).
   - Whether the original hypothesis still stands.
   - Open questions remaining.
   - Recommended next action: clear marker, raise a new event,
     promote to pattern, deprecate, or hold.

### Stage 1.4 — Deterministic enrichment (only when `--adversarial`)

**Pre:** Stage 1 produced a batch of per-target findings.
**Post:** each entry in the batch carries a signals payload.

This step is cheap and LLM-free. For each entry, compute and attach:

| Signal | Source | Purpose |
|---|---|---|
| `existing_slug?` | `ideas_lib` projection (grep the ledger for slug + alias matches) | Catch literal duplicates the orchestrator missed |
| `subsystem_kind_frequency` | Count occurrences of the entry's `subsystem_kind` in the ledger | Flag never-seen-before kinds (likely typo or wrong taxonomy) |
| `adr_keyword_hits` | Grep `ai-docs/decisions/*.md` titles for entry keywords | Surface "ADR already covers it" candidates |
| `slug_token_overlap` | Token compare against all existing intake slugs (highest-overlap neighbors) | Surface near-duplicates that warrant a `composes_with` edge |

These signals **do not make the verdict** — they are context the
Stage 1.5 LLM uses to judge. The five failure modes the gate
targets (duplicates, wrong-kind, missed-edge, ADR-covered, evidence-
free impact claims) overlap with what grep can answer, but the
*legitimacy* of each call is semantic.

### Stage 1.5 — Adversarial LLM judgment (only when `--adversarial`)

**Pre:** the batch + enrichment payloads are ready.
**Post:** a per-entry verdict (`accept` / `revise` / `drop` / `other`)
with a one-line rationale.

Delegate to a sub-agent with:

- **Sub-agent type:** `general-purpose` by default (universally
  available). Override via `.claude/docs/review-lane.md` if the host
  project has a custom adversarial agent.
- **Batch ceiling:** 8 entries per LLM call. Batches larger than 8 are
  chunked. (The 8 is a calibration starting point; bump if you see
  rubber-stamping at the tail of long batches.)
- **Context delivered to the sub-agent:**
  - The chunk's batch JSON (8 entries max), with the orchestrator's
    Stage 1 synthesis attached.
  - The deterministic enrichment payload from Stage 1.4.
  - The ledger's current `subsystem_kind` frequency map (~10 lines).
  - A short snippet of `idea-ledger.md`'s schema rules so the gate
    can reason about marker / state legality.
- **Verdict shape per entry:** `accept` | `revise` | `drop` | `other`,
  plus a one-line rationale. The five reference failure modes
  (`duplicate`, `wrong-kind`, `missed-edge`, `adr-covered`,
  `evidence-free`) focus the sub-agent's attention; `other` is
  reserved for cases the rubric doesn't cover.

The dispatch prompt must tell the sub-agent that its output is judged
only by that per-entry verdict shape and whether the rationale cites the
delivered enrichment signals. Do not ask for a balanced review essay.

Terminal behavior:

- `accept` → entry flows to Stage 2 unchanged.
- `revise` → orchestrator re-runs Stage 1 for that one entry once,
  showing the sub-agent's rationale as input. The realistic outcome of
  one revision pass within the same context tree is "no meaningful
  change" — this is a one-shot quality bar, not a feedback loop.
  - **Second pass still non-accept:** defaults to `drop` with the
    report line citing both rationales. `--accept-on-loop` overrides
    this (the entry is written with a `lesson` event flagging both
    rationales so the user can audit later).
- `drop` → entry is excluded from Stage 2; the report logs the
  rationale so the user can override manually.
- `other` → treat as `revise` unless the rationale explicitly says
  "accept anyway".

`--adversarial` is **off by default in v1**. Flip on after the
calibration exit criterion is met (three mature runs catch at least
one real miss the orchestrator would have shipped, with verdict
latency < 30s per chunk). See ADR 0013 for the broader idea-tracking
contract.

### Stage 2 — Write research events

**Pre:** per-target findings in hand. **Post:** one `note` event per
target appended to ledger.

For each target, append a `note` event with `summary` prefixed
`research:` plus the synthesis. Sources appear as a citation list at
the end of the summary.

```bash
.venv/bin/python .claude/skills/track-idea/scripts/track.py event <slug> \
  --kind note \
  --summary "research: <synthesis paragraph(s)>. Sources: <url>, <path>, <doc-title>."
```

When the research warrants a marker clearance and the user requested
it via flag, also append a marker event:

```bash
.venv/bin/python .claude/skills/track-idea/scripts/track.py event <slug> \
  --kind marker --markers-removed needs-research \
  --summary "research complete: <one-line why>"
```

If `--clear-underdeveloped` is set AND the research showed the idea is
now well-formed, append the same marker event with
`--markers-removed underdeveloped`.

If the research surfaces a reusable rule or invalidates the original
hypothesis, append a lesson through the same writer:

```bash
.venv/bin/python .claude/skills/track-idea/scripts/track.py lesson <slug> \
  --title "<short lesson title>" \
  --body "Rule: <rule>. Why: <evidence>. How to apply: <future use>."
```

Paste every `track.py` output line into the final report. If a command
returns non-zero, stop writing additional events for that slug and
report the exact failure.

### Stage 3 — Render the report

**Pre:** writes complete. **Post:** user sees what was researched and
what was decided.

```
# Maturity pass (now: <iso>, mode: <A|B|C>, n targets: N)

## <slug-1> — <title>
Before: state=<X>, markers=<list>
Research: <synthesis>
Sources:
- <url|path>
- ...
Decision: <cleared needs-research | left as-is | suggest promotion | suggest deprecate>

## <slug-2> ...
```

End with a *suggested next steps* section that names the most-actionable
follow-ups across the batch (e.g., "`hydration-fast-path` is
promotion-ready per `.claude/docs/pattern-library.md` because
adoption_count is now 1"; "consider `/decide` on `<slug>` if the
finding is binding").

### Stage 4 — Stop

Do not auto-promote to Tier 2. Do not auto-deprecate. Surface the
recommendation; the caller decides.

## Non-goals

- Generating new ideas (`/brainstorm-ideas`).
- Promoting to Tier 2. The promotion workflow is planned but no
  `/promote-idea-to-pattern` skill is installed in this kit; cite
  `.claude/docs/pattern-library.md` and stop.
- Editing a pattern's Research log section directly. (Future work: when
  patterns exist in the library, also append to the pattern's
  Research log + update `last_research_at`. Out of scope for v1.)
- State transitions beyond marker changes. Recommend, don't execute.
- Agentic spec-conformance validation in the *formal* sense (that's
  the `skill-spec-conformance-validation` open gap). This skill is the
  manual surrogate.

## When things go sideways

| Symptom | Action |
|---|---|
| `--all-needs-research` finds zero targets | Exit 0; report "no ideas carry needs-research" |
| Idea not found by slug | Exit 1 with usage; suggest `/track-idea list` to find the right slug |
| `--external-research` requested but offline | Skip external lookups; do internal-only research and note the limitation in the summary |
| Research conclusion is "no new info" | Still write a `note` event recording the negative finding — future readers benefit from seeing that the rabbit hole was checked |
| Marker clearance requested but research shows the idea is still under-researched | Refuse the clearance; surface the open questions and recommend a follow-up pass |
| Research surfaces a contradiction with the original hypothesis | Log it as a `lesson` record (rule + why + how to apply) in addition to the `note` event |
| `track.py` exits non-zero while writing a note, marker, or lesson | Stop writes for that slug, paste the exact output, and leave markers unchanged |
| `--adversarial` requested but `.claude/docs/review-lane.md` names a missing sub-agent type | Fall back to `general-purpose` and note the substitution in the report |
| Adversarial chunk returns a verdict for an unknown id | Treat as `other`; surface in the report so the user can decide |
| Adversarial verdict latency > 30s per chunk for three consecutive runs | Lower the batch ceiling (e.g. 8 → 4) and re-measure before keeping the gate on by default |
| Revision pass produces the same output as the original | Apply the default terminal behavior (`drop`); SKILL note clarifies this is the expected case |

## Replay case

After material edits to this skill, prove the ledger-write boundary in a
temporary project and paste the real output:

```bash
TMPDIR=$(mktemp -d)
mkdir -p "${TMPDIR}/.claude/ideas"
.venv/bin/python .claude/skills/track-idea/scripts/track.py intake replay-idea \
  --project-root "${TMPDIR}" \
  --title "Replay idea" \
  --origin "skill-replay" \
  --subsystem-kind "skill" \
  --quality-markers needs-research \
  --summary "Replay fixture for mature-existing-ideas."
.venv/bin/python .claude/skills/track-idea/scripts/track.py event replay-idea \
  --project-root "${TMPDIR}" \
  --kind note \
  --summary "research: replay note. Sources: local fixture."
.venv/bin/python .claude/skills/track-idea/scripts/track.py show replay-idea \
  --project-root "${TMPDIR}" \
  --quiet-on-list-fields
```

Do not run the replay against the real project ledger.

## Repository layout

```
.claude/skills/mature-existing-ideas/
└── SKILL.md                  # this file — orchestrator
```

The orchestrator does the research; `track-idea/scripts/track.py` writes
the events deterministically.

## Cross-references

- Schema: `.claude/docs/idea-ledger.md`
- Adversarial-gate sub-agent override (optional host config):
  `.claude/docs/review-lane.md` (default: `general-purpose`)
- Sibling skills: `/track-idea`, `/find-orphaned-ideas`, `/brainstorm-ideas`
- Open gap (formal spec conformance): ledger entry
  `skill-spec-conformance-validation`
- ADR motivating this system:
  `ai-docs/decisions/0013-idea-tracking-system.md`
