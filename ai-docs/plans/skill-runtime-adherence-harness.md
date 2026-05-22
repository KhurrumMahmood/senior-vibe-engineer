---
name: skill-runtime-adherence-harness
title: Skill runtime-adherence harness (research aspiration)
status: draft
date: 2026-05-22
authors: []
motivating_decision: null
successor_spec: null
subsystems: []
workflows: []
---

# Skill runtime-adherence harness (research aspiration)

> **Research aspiration, not a build.** Graduated from the
> `skill-runtime-adherence-harness` ledger intake to consolidate three
> refinements that outgrew event notes. No execution is committed; §3–4 are
> deliberately deferred until a decision to build is taken.

## 1. Scope & Bounds

A skill is prose an agent is *trusted* to execute. Under real-world noise —
weaker models, or any model on a long procedure — steps get skipped and
constraints (`not_for`, guards, per-item coverage) get dropped. Static
artifact coherence (the IAC bands) proves a skill is *well-formed*; it cannot
prove the agent *did what the skill says* at runtime. This is the second of
three orthogonal skill-health axes:

1. static artifact coherence — IAC Bands A/B/C (separate work)
2. **runtime adherence — this note** (does the agent DO the steps under noise)
3. cross-model execution portability — folded in below as an ablation method

**In scope.** Mechanisms that raise the *floor* on "all the steps actually
ran": declared-evidence enforcement, completeness primitives, a post-hoc
verifier, and the ablation method that says which of those each skill (and
each model tier) actually needs.

**Out of scope / non-goals.** Not a replacement for `/plan-skill` dogfooding
— that proves a skill *can* work once; this guards that it *keeps* working
under noise. Not the static IAC bands. Not a blanket per-skill mandate:
depth ladders by stakes × executor tier, and cheap skills stay prose-trust.

## 2. Success Criteria

- A skill can **declare** the evidence its run must produce (`produces:` /
  `evidence_required:` — already typed in `skill_meta.py` lines 67–74, today
  optional) and a deterministic check confirms that evidence was actually
  produced, not self-reported.
- For multi-item work the **completeness ledger lives outside the agent's
  context** (a primitive it calls), so "did 7 of 10" is structurally
  impossible to land green.
- The success oracle is **deterministic and model-agnostic** — so it can
  double as the fixed yardstick for cross-model ablation.
- Adding the harness to a skill is **cheaper than the failure it prevents**
  (`max_overhead:` honored).

## 3. Impact Map

_Deferred — greenfield research aspiration; nothing is being modified yet.
Fill via `/impact-feature` if this graduates to a build._

## 4. Blast Radius

_Deferred — see §3._

## 5. Architecture Fit

**The harness strength ladder** (weak → strong). Only the bottom two rungs
are *portable* — they prove performance identically on any executor:

| Rung | Mechanism | Determinism |
|---|---|---|
| self-reported checklist | agent says it did the steps | none (model-coupled) |
| independent verifier pass | a *fixed strong* model grades the run adversarially | model-coupled; never the model-under-test |
| declared-evidence enforcement | run must emit its declared artifacts; a script checks them | deterministic |
| procedure-in-a-primitive | the step *is* a tool call; the tool carries the guarantee | deterministic |

**Primitive ↔ gate duality** (the core move). "Push control flow into code"
must **not** mean taking the loop away from the agent — an agent in a
tool-runtime outperforms a bare one, so trading its agency for determinism
is a bad deal. Instead the agent keeps driving and calls an orchestration
**primitive** that holds the guarantee: determinism moves *into a callable
tool*, not *out of the agent*. That yields two postures that reinforce:

- **Inline primitive (proactive)** — a for-each / task-ledger tool the agent
  invokes so it *can't* lose the count; the tool remembers, not the context
  window. `TodoWrite` is already this shape; the `tools/` orchestrator-worker
  (`cli-agent-tool.md`) is the heavier version; the resilient-agent
  architecture (fresh-context loops + failure partitioning) is the
  noise-hardened version.
- **Post-hoc gate (reactive)** — the deterministic evidence check that
  confirms all N happened, and that can also police *primitive usage*
  ("10-item step, agent never called the orchestration tool").

Two constraints fall out of "easily call":

1. **Ergonomics are load-bearing.** If the primitive is clunkier than winging
   it, the agent routes around it and the guarantee evaporates — the same
   failure as a dormant lint, one layer up: *a primitive nobody calls
   orchestrates nothing.*
2. **The failure mode moves; it doesn't vanish** — from "tracked the loop
   badly" to "forgot to use the loop tool." Net progress (a tool call is
   easier to get right than a mental ledger), but it's why the skill body
   must make the primitive the obvious move and the gate must verify it was
   used.

**Cross-model = ablation, not a validation matrix.** Vary the executor to
test whether each check earns its keep: no model needs it → cut; all need it
→ harden into a primitive; only weak models need it → model-tier scaffolding.
*A check's existence ≠ its necessity.* Ablation **presupposes** the
deterministic oracle above — you can't measure "did removing the check hurt?"
without a model-agnostic yardstick — so the ordering is forced: **build the
oracle first, then ablate.** Reassuringly, the oracle is the boring
evidence-enforcement rung we'd build anyway.

**Reuses existing es2 machinery.** This is the third use of the
block-on-declared / coverage-ratchet meta-pattern already shipped in
`run_skill_smokes.py` (`--require-all`) and `skill_meta.py lint` (`--strict`):
block on what's *declared*, report the coverage ratio, ratchet the floor over
time. The "harness layer" is named as kernel-level in
`quality-coordination-kernel.md`. Depth ladders on stakes × executor-tier,
consistent with the lifecycle × stakes model (ADR 0020).

## 6. Open Decisions

1. **Make `produces:`/`evidence_required:` load-bearing, or keep opt-in?**
   (~8/66 skills declare them today.) Leaning load-bearing via the same
   coverage-ratchet used for smokes — a declared, enforced evidence contract
   is what makes the proof *portable* across models. The fork is whether to
   promote now or after the oracle exists.
2. **What is the first orchestration primitive?** `TodoWrite`-as-ledger is
   free but generic; a skill-specific for-each/map primitive carries a
   stronger guarantee but costs ergonomics design. Ablation should pick the
   minimal set per model tier rather than building speculatively.
3. **Where does the verifier rung live, if at all?** A fixed strong model
   grading runs is the most expensive rung and the only LLM-coupled one above
   the floor — likely reserved for the highest-stakes skills only.

Candidates for `/decide` once the work leaves research status.

## 7. Promotion Notes

_Unpromoted — research aspiration. Promote via `/plan-spec` only if a
decision to build is taken._
