---
id: "0020"
namespace: core
title: Lifecycle- and Stakes-Gated Standard Activation
status: proposed
date: 2026-05-21
deciders: []
supersedes: []
superseded_by: null
revisit_when: ["a second host or a lifecycle transition requires the standards activation matrix to make a promotion or demotion decision"]
applies_to: [".claude/skills/find-standard-gaps/"]
embodied_by: ["skill:orient", "skill:find-standard-gaps"]
tags: [standards, lifecycle, project-stage, stakes, activation, baseline, orientation, north-star]
related_smell: null
related_pattern: null
---

# Lifecycle- and Stakes-Gated Standard Activation

## Context

ADR 0018 named the outward-facing quality axis and noted, in one line, that
controls should "stage to maturity." This ADR turns that line into a mechanism,
because the single most common production failure in AI-grown code is not a
missing control — it is **forgetting to raise the bar when the project crosses
a threshold** (prototype → relied-upon; internal → exposed).

Two framing corrections drove the design:

- **The gap is activation, not knowledge.** General model training already
  covers production standards. What suppresses them is the operating *mode* —
  "hit the goal somehow," inheriting whatever (often vibe-coded) standards the
  surrounding project already has. The ecosystem's job is to *activate* latent
  senior-engineer judgment at the right moment and bar, not to store facts the
  model already holds.

- **There is a substantial always-on baseline.** An earlier sketch made the
  prototype stage near-empty ("move fast, few standards"). That is wrong: the
  dominant failure in AI-grown code is maintainability chaos — rampant
  duplication, inconsistent implementations, fragile one-area fixes. The cure
  (DRY / SOLID / consistency — most of the *existing* ecosystem) must apply even
  to a prototype. A prototype may be unfinished; it may not be insane.

Two axes, not one:

- **Maturity** — how real is the reliance (prototype → first real users / data →
  production / relied-upon).
- **Stakes / exposure** — how much a failure costs and how exposed it is
  (internal-trusted → external-untrusted → public-adversarial / high-uptime /
  regulated).

These are independent. The reference host adaptation is the proof: it is *quasi-live*
(high maturity) but an *internal, trusted-operator tool* with modest uptime
needs (low stakes). It must not be buggy, but it should never be held to the
"always under fire, like Google" bar. Maturity alone would mis-rank it.

And concerns are **not binary**. Most have a *depth ladder*: a cheap
common-sense rung and progressively heavier rungs. Prompt-injection defense runs
from structural delimiters + parser-strip + a never-obey-crawled-content rule
(cheap, common-sense) up to a second model pre-screening all incoming text for
safety (expensive). **Stakes selects which rung is appropriate** — not merely
whether the concern is "in scope." For a low-stakes internal tool, the
common-sense rung is the *appropriate ceiling*, not just a floor.

## Decision

Model standard activation as **baseline + depth-laddered, two-axis-gated rungs**.

1. **Baseline ("Sanity") — always enforceable, every project, every stage.**
   - Maintainability / consistency: DRY, SOLID, no rampant duplication,
     consistent implementations, universal (not one-area) fixes — the bulk of
     the existing ecosystem.
   - The **common-sense rung** of safety concerns that are cheap and have "no
     reason not to" from day one: structural prompt-injection delimiters, input
     hygiene, no hardcoded secrets, no obviously-unauthenticated side-effectful
     endpoints, parse-and-validate before fetching a URL.
   - Never gated off. This is the floor that is never optional.

2. **Progressive rungs declare an activation threshold on both axes.**
   - A concern may have several rungs; each heavier rung carries
     `{min_maturity, min_stakes}` and a cost. A rung activates only when the
     project meets **both** thresholds — so a heavier rung's cost is paid only
     when maturity *and* stakes justify it.
   - Some rungs are maturity-driven (reversible migrations, backups), some
     stakes-driven (rate-limiting / DDoS, threat modeling, second-model input
     screening); many need both.

3. **The failure modes are symmetric — guard both.**
   - **Under-defending:** a prototype-grade control shipped into a relied-upon,
     exposed context without upgrading (the stated biggest hole).
   - **Over-defending:** gold-plating a low-stakes internal tool as if it were a
     public adversarial service — wasted effort and complexity. Stakes-gating
     prevents *both*: it raises the bar on the way up and *caps* it on the way
     down.

4. **Each `find-standard-gaps` standard declares its activation:** `baseline:
   true`, or a set of rungs each with `{min_maturity, min_stakes}`. The scanner /
   review-avatar lane enforces a rung only when the project's declared
   (maturity, stakes) meet it; baseline always runs. The harvest skill tags
   every harvested standard with this activation shape.

Project state is **declared, inferred, and re-confirmed** — all three:

- **Declared:** an explicit project-state surface (maturity + stakes), analogous
  to `environment=dev/production` in `.env`. The project owns it.
- **Inferred (push):** heuristics flag candidate transitions ("this looks more
  mature / exposed than its declared state — a new unauthenticated write
  endpoint, first real-user data, a public deploy") and *ask* the user to
  confirm and run `/orient`. Inference proposes; the human disposes — the agent
  cannot read stakes from code alone.
- **Pull:** `/orient` on demand re-establishes state via orientation questions
  (real users or test data? internal or public? blast radius? uptime needs?).

## Alternatives considered

- **Single-axis linear maturity ladder.** Rejected: conflates "how live" with
  "how high-stakes." It would over-burden a quasi-live internal tool and
  under-protect an early public service. The reference host adaptation is the counterexample.
- **Near-empty prototype baseline ("move fast, no standards").** Rejected: the
  dominant real-world failure in AI-grown code is maintainability chaos, not
  under-engineered safety. The Sanity baseline must bind even prototypes.
- **Treat each concern as binary (in scope / out of scope) per stage.**
  Rejected: it loses the depth ladder. Prompt injection is *always* in scope at
  its common-sense rung and *rarely* in scope at its second-model rung; the unit
  that gates is the rung, not the whole concern.
- **Auto-advance stage with no human confirm.** Rejected as the sole mechanism:
  stakes / exposure are not reliably inferable from code. Inference may *propose*
  a transition; a human confirms it.
- **Per-file / per-area stage as the primary unit.** Deferred: the primary state
  is project-level (declared maturity × stakes). Per-area exceptions are an
  override (e.g. a prototype-grade debug surface inside a production app), not
  the base unit — and the baseline already catches the common case ("no
  unauthenticated side-effectful endpoint" is baseline, so a stray debug route
  is flagged without needing per-area state).

## Consequences

- **Easier:** every standard says *when* it applies and *at what depth*; a
  prototype run is quiet on production concerns; a low-stakes tool is not
  gold-plated; the baseline is unambiguous and always on. The most-skipped move —
  re-deciding the bar at a transition — becomes a system event, not something a
  human must remember.
- **Harder:** someone must declare and maintain (maturity, stakes); standards
  authors must classify each rule (baseline vs which rung); the inference
  heuristics and `/orient` flow must be built and tuned.
- **Reference host adaptation worked classification:** maturity ≈ live / relied-upon (internal);
  stakes ≈ **low** (internal, trusted operators, modest uptime). ⇒ enforce
  baseline (Sanity + the common-sense safety rung) and the maturity-driven
  correctness rungs (don't lose data) — but treat the *common-sense* rung as the
  appropriate ceiling for stakes-driven concerns. Concretely, from the
  2026-05-21 audit: the cheap wins (SSRF chokepoint, closing unauthenticated
  side-effectful routes, `ppc_code_is_safe` at the write boundary, prompt
  delimiters) are baseline-worthy — *do them*; the heavy adversarial rungs
  (broad rate-limiting / DDoS infrastructure, a second model pre-screening all
  crawled text for prompt-injection safety) are **not** required at a quasi-live
  internal service's stakes — *do not* gold-plate them.

## Verification

- `find-standard-gaps` standards carry an activation field (`baseline: true` |
  rungs with `{min_maturity, min_stakes}`); `scan_coverage.py` gates progressive
  rungs by the project's declared state; baseline always runs.
- A declared project-state surface exists (maturity × stakes), analogous to
  `environment`.
- `/orient` exists (pull); an inference pass flags candidate transitions for
  confirmation (push).
- A regression check proves a prototype-classified project is *not* flagged for a
  stakes-gated rung, and that raising its declared stakes activates that rung.
- **Proposed** until: the state surface + one gated scan exist, *and* the reference host adaptation is
  classified and its scan reflects "live / low-stakes" (baseline + common-sense
  rungs, no gold-plating). Pairs with ADR 0018 (the axis), ADR 0019 (trust
  boundaries — whose common-sense rung is baseline), and the harvest skill (which
  tags each harvested standard with its activation shape).
