# success-game harvest — March 2026 transcript mining

Source: `~/Projects/success-game/` (READ-ONLY). One long 2026-03-16 design
conversation about a private host project (referred to here as **host-a**),
plus three memory/backlog siblings. Files:

- `initial-chat.md` (762 ln) — full conversation: requirements source of
  truth, requirements-as-state propagation, domain agents, case law,
  skill crystallization, token economics.
- `initial-chat-expanded.md` (714 ln) — same conversation, tail portion with
  timestamps; lines cited below from `initial-chat.md` unless noted.
- `simpler-alt-inital-chat.md` — early alternative reply; per-feature
  requirements directory sketch.
- `project_requirements_propagation_system.md` — the synthesis doc the
  session wrote (concept document for the whole system).
- `project_ralph_wiggum_context_mgmt.md` — fresh-context loops, sub-agent
  context multiplication, progressive extraction with failure partitioning.
- `project_autoresearch_backlog.md` — autonomous experiment-loop idea.

Verdicts: **NEW** (not in ledger, not built), **ALREADY-BUILT** (exists as a
skill/doc/practice in this repo — historical lineage), **ALREADY-LEDGERED**
(a ledger entry already owns the concept). Intaken candidates are marked.

---

## Candidates

### 1. requirements-traceability-records — NEW → INTAKEN
Per-feature prescriptive requirement records with a fixed schema —
Behavior / Why / Decision / Implementation ref / Test ref — so each
requirement is traceable to the code and test that realize it, and a
gap-finder query becomes possible: "this requirement changed; which
affected code locations lack covering tests?" Distinct from the ledger's
`docs-to-code-dependency-graph` (which owns the DAG/dirtiness mechanics):
this is the node schema and the coverage query.
Cite: `initial-chat.md` 64-82 (R-DISC-003 example schema), 437-438
(coverage gap finder as "killer feature"); `simpler-alt-inital-chat.md`
22-30.

### 2. Requirements-as-source-of-truth propagation engine — ALREADY-LEDGERED
"Requirements are core state; code is the projection; changes propagate"
(the React one-way-data-flow analogy), with the key softening that
projection need not be deterministic, only **verifiable** (tests gate,
human reviews). Owned by ledger entries `docs-to-code-dependency-graph`,
`make-change`, and `propagate-convention-change`. The verifiable-not-
deterministic principle is worth quoting into those entries' eventual
design docs.
Cite: `initial-chat.md` 228-230, 296-330, 341-457 (full product sketch),
372-375 (verifiable > deterministic).

### 3. Decision log / decisions as case law — ALREADY-BUILT
Append-only decision records with Context/Options/Decision/Revisit-if;
three precedent types (bright-line rules, standards, case law); agents
search precedent on ambiguous calls and distinguish when facts differ.
Independently rebuilt as `ai-docs/decisions/` ADRs + `.claude/docs/
precedents.yml` ("updateable implementation case law"). Pure lineage —
this transcript is the earliest articulation.
Cite: `initial-chat.md` 181-189, 467, 509-537.

### 4. code-mode-tool-invocation — NEW → INTAKEN
Design position: LLM-emitted code that *calls* tools is more reliable than
native tool-call JSON for composing calls, conditional logic, and batch
operations; reserve native tool calling for single-shot decisions.
host-a's agents used structured-JSON decisions and native tool calls;
neither was code-mode. No ledger entry covers tool-invocation style for
the ecosystem's own harnesses/scout dispatch.
Cite: `initial-chat.md` 20, 87-104.

### 5. Sub-agent agentic RAG over docs — ALREADY-BUILT
Cheap sub-agents read many doc/requirement files and return a coherent
picture without polluting main context. Rebuilt as this repo's sub-agent
posture, Explore agents, `/query-patterns` + `query-patterns-inline`.
Cite: `initial-chat.md` 113-115, 146-149.

### 6. Doc-size thresholds + docs need refactoring like code — ALREADY-BUILT / LEDGERED
Leaf doc files capped (~150 ln) so a sub-agent reads one in a single shot;
significant changes require refactoring the doc tree for coherence.
Covered by `/find-rule-surface-drift` (oversized always-loaded files) and
ledger `module-size-band` (context-window-economics sizing).
Cite: `initial-chat.md` 111-121, 131-144.

### 7. Path-glob conditional context injection — ALREADY-LEDGERED
Auto-load the relevant requirements/rules when touching matching code
("rules folder as the bridge between requirements existing and being
consulted"). Ledger `context-triggered-memory-injection` owns the concept
(step-keyed variant); the path-glob trigger is a sub-case worth noting
there.
Cite: `initial-chat-expanded.md` 24-32.

### 8. Parallel-agent coordination file + semantic-conflict insight — ALREADY-LEDGERED
Append-only `COORDINATION.md` notes between parallel worktree agents;
locks keyed to worktree branch; and the durable observation that the
dangerous conflict is **semantic** (agent A adds a requirement
contradicting what agent B relies on) — no locking scheme catches it, only
human review. Ledger `agent-connector-framework` owns the surface; the
semantic-conflict observation deserves to ride along when that matures.
Cite: `initial-chat.md` 212-214, 259-273.

### 9. agent-conflict-constitution — NEW → INTAKEN
When domain/review agents disagree (performance vs accessibility vs
design), resolution needs an explicit priority hierarchy ("constitution"):
higher-priority concern wins by default, lower-priority agent must satisfy
its goals within that constraint, and the compromise is logged as new
precedent. Without it: deadlock or whoever-runs-last-wins. Ledger has
`role-agents-design` / `role-based-review-avatars` (the agents) and
`composable-goal-constraint-router` (goal/floor/veto routing) but nothing
owns inter-agent conflict resolution + compromise-as-precedent.
Cite: `initial-chat.md` 489-505, 533-537 ("Priority applied" field).

### 10. Standard vs coincidence; initial crystallization — ALREADY-BUILT
"If your project happens to use 8px spacing everywhere, that's not a
standard — it's a coincidence that will eventually be violated"; an LLM
produces 10 valid versions, picking one creates a consistency obligation
that must be *declared*, not just observed. Rebuilt as `/decide`,
canonical-patterns, `/prevent-regression`; ledger `positive-pattern-mining`
covers mining observed regularities into declared patterns. The
coincidence-vs-standard one-liner is a quotable lineage note.
Cite: `initial-chat.md` 541-551.

### 11. Retroactive requirement ripple — ALREADY-LEDGERED
Adding a cross-cutting requirement post-hoc (e.g. accessibility): blast
radius → conflict detection → compromise negotiation → prioritized
rollout. Ledger `propagate-convention-change` owns the mechanism.
Cite: `initial-chat.md` 470-475, 553-571.

### 12. Skill crystallization cycle + injection — ALREADY-BUILT
Fluid reasoning → learned patterns → deterministic skills (System 1/2);
agents promote recurring judgments into lint rules/test utilities and
inject them into host CI ("the skill lives with the agent, but its effect
lives in the codebase"). This is the repo's mantra and the GUARD tier
(`/prevent-regression`, `/harvest-learnings`). Strong lineage: the
transcript is a clean early statement of the ecosystem's core thesis.
Cite: `initial-chat.md` 645-707, 725-757.

### 13. Skill-rot audit — ALREADY-LEDGERED
"Periodically audit existing skills against updated requirements — a skill
correct under the old design system might be wrong under the new one."
Ledger `guard-false-alarm-accounting` owns guard re-auditing; the
trigger-on-upstream-requirement-change nuance could enrich it.
Cite: `initial-chat.md` 677-679.

### 14. Declining cost-per-check curve as system health metric — NEW (report only)
Token economics as the make-or-break constraint: the system is healthy iff
agents do *less* LLM work over time (Day 1 $$$ reasoning → Day 90
deterministic ¢ → Day 180 amortized across projects). Adjacent to ledger
`spend-telemetry` (cost tracking) and `tool-bias-capability-gaps`;
borderline — left as a report note to fold into `spend-telemetry` when it
matures, rather than a separate intake.
Cite: `initial-chat.md` 723-733, 749-751.

### 15. Library specificity tiers (core / domain / project) — NEW (report only)
Crystallized standards organized by specificity: universal core (every
project, fully deterministic), domain (project-type, opt-in), project
(bespoke, where LLM reasoning concentrates). Relevant to this kit's
productization story but adjacent to `cross-language-default-suites` and
`pack-installer`; borderline — report only.
Cite: `initial-chat.md` 716-721, 736-741.

### 16. Provenance/impact graph storage progression — ALREADY-LEDGERED
"Why is this button 44px?" provenance traversal and "change the grid,
what breaks?" impact traversal; storage progression markdown → SQLite
recursive CTEs → embedded graph DB (Kuzu) → server graph DB only at
multi-team scale. Ledger `code-knowledge-graph-substrate` +
`docs-to-code-dependency-graph` own it; the staged-storage progression is
a useful design note for both.
Cite: `initial-chat.md` 155-163, 564-570, 594-634.

### 17. intentionality-annotation-pass — NEW → INTAKEN
Bootstrapping prescriptive requirements from an existing codebase:
reverse-engineering yields only *descriptive* requirements ("what it
does"), which diverge from prescriptive ones wherever there's a bug. The
high-value step is a human triage pass over the draft: **intentional /
bug / intentional-but-wrong**. `/explain-code` and `/project-interview`
produce the inputs but nothing in the ecosystem owns this three-way
annotation protocol.
Cite: `initial-chat.md` 234-241; `project_requirements_propagation_system.md`
§Bootstrapping.

### 18. failure-partitioned-iteration — NEW → INTAKEN
Build-run-fix harness loop: attempt batch work with the current script;
partition successes (→ output) from failures (→ failure log with context);
group failures by failure mode; develop a targeted fix per mode; re-run on
failures only; repeat until done or diminishing returns. Each iteration's
context is bounded to one failure class instead of the whole problem.
Generalizes beyond extraction to any batched transformation/sweep —
composes with ledger `batched-transformation-harness` and
`skill-run-state-resume`.
Cite: `project_ralph_wiggum_context_mgmt.md` 26-35.

### 19. Fresh-context loops with file-persisted state — ALREADY-LEDGERED
Ralph Wiggum pattern: outer loop of fresh sessions, `progress.md` +
`learnings.md` persisted between them; sub-agents as context
multiplication. Ledger `skill-run-state-resume` and
`phase-boundary-context-reconstruction` own the territory.
Cite: `project_ralph_wiggum_context_mgmt.md` 11-22.

### 20. experiment-loop-optimization — NEW → INTAKEN
Autonomous experiment loop applied to tuning AI workflows: propose change
→ benchmark → keep winners → revert losers → repeat (autoresearch
pattern). In host-a it targeted CSS-selector strategies; the durable form
for this ecosystem is benchmark-driven tuning of detector thresholds,
prompt variants, and skill phrasing where a scoring script exists. Distinct
from `simulation-gated-promotion` (which simulates before promoting a
rule, no benchmark loop).
Cite: `project_autoresearch_backlog.md` 7-11.

### 21. Ping-pong regressions = implicitly-coupled requirements — lineage note
Fix-A-breaks-B cycles are a symptom of requirements that are implicitly
coupled but not explicitly connected; the layered model (human reqs →
technical reqs → architecture decisions → code) plus cross-references
makes the coupling visible. Folds into candidates 1/2; also early lineage
for this repo's blast-radius posture (`/impact-feature`).
Cite: `initial-chat.md` 217-229, 277-294.

### 22. Branch-based requirement blast-radius what-if — NEW (report only)
Version requirements like code (PRs, blame, rollback) and use branches for
what-if analysis: "change the design language on a branch, see the blast
radius before committing." Cheap note for `docs-to-code-dependency-graph`;
not a standalone intake.
Cite: `initial-chat.md` 432-435.

---

## Tally

- Candidates examined: 22
- NEW: 9 (of which 6 intaken: requirements-traceability-records,
  code-mode-tool-invocation, agent-conflict-constitution,
  intentionality-annotation-pass, failure-partitioned-iteration,
  experiment-loop-optimization; 3 report-only: 14, 15, 22)
- ALREADY-BUILT (historical lineage): 6 (3, 5, 6, 10, 12, plus the
  self-dogfooding property at `initial-chat.md` 598-600)
- ALREADY-LEDGERED: 7 (2, 7, 8, 11, 13, 16, 19)

All intakes tagged `success-game-harvest`, origin `convo`.
