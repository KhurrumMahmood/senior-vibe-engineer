---
id: "0018"
title: Outward Facing Quality Dimensions
status: proposed
date: 2026-05-21
deciders: []
supersedes: []
superseded_by: null
applies_to: []
tags: [security, resilience, observability, data-privacy, cost, standards, review-avatars, posture]
related_smell: null
related_pattern: null
---

# Outward Facing Quality Dimensions

## Context

The skill ecosystem is deep on **inward** quality — maintainability,
structure, layering, duplication, naming. Every project AST lint and every
architectural smell is structural. There is near-zero coverage of
**outward-facing** quality: how the system behaves under a hostile input, a
failing or compromised dependency, an operator paged at 3am, a privacy
obligation, and a bill.

A read-only audit of the host project (pnci-pricing, 2026-05-21) confirmed the
gap is not theoretical. Three independent scouts found: user-controlled
`bypass_proxy` enabling SSRF to the cloud-metadata endpoint; 10+ unauthenticated
`/debug/*` routes live in production regardless of `DEBUG`; and eight `exec()`
sites running LLM-generated Python with no import restriction. None of these
were flagged by any existing lint or smell, because no lint or smell looks
outward. The implicit security the project *does* have (Django ORM,
autoescaping, env-var secrets) is a property of the framework, not of anything
the ecosystem names, measures, or guards.

The question: should outward-facing quality be a **named, first-class axis**
with its own tracking, or stay handled ad hoc per feature?

## Decision

Name outward-facing quality as a first-class second axis with five faces —
**security, resilience, observability (application + product), data/privacy,
cost/abuse** — and track it with a two-tier model:

- **Floor (deterministic, always-on).** Rules an AST or grep can check ("outbound
  calls set a timeout", "no `eval`/`exec` on untrusted input", "no
  `verify=False`", "service code logs, not prints") are declared as
  `find-standard-gaps` standards (`ast`/`grep` detectors) and coverage-checked
  across the tree.
- **Ceiling (judgment-heavy, manual).** Rules no AST captures ("authorize against
  the object, not just the user", "no PII in logs or prompts", "expensive
  endpoints are abuse-bounded", "external content is contained at the boundary",
  "user friction is instrumented") are declared `kind: manual` standards — the
  declared baseline stays *complete*, and these are what the role-based
  **review-avatar lane** checks.

`senior-engineer-posture.md` §4 carries the framing and instincts; the standards
file carries the floor; the avatar lane carries the ceiling. The three are wired
together: the manual standards are literally the avatar lane's checklist.

## Alternatives considered

1. **Status quo — handle each outward concern ad hoc per feature.** Rejected:
   the audit shows this produces silent, systemic gaps. No one owns the axis, so
   security decays as endpoints, fetch paths, and exec sites accumulate.
2. **One-time security audit + a static checklist.** Rejected as the *primary*
   mechanism: audits are point-in-time and coverage decays the moment a new
   endpoint skips the check. The ecosystem mantra is "convert one-off
   discoveries into repeatable guardrails" — an audit is the discovery, the
   standards floor + regression guards are the conversion.
3. **Adopt a full SAST/DAST stack.** Rejected for now: heavyweight, noisy,
   language-coupled, and blind to the novel surfaces that matter most here (LLM
   prompt injection, generated-code execution, crawl/LLM cost abuse). The
   floor/ceiling split is lighter and AI-native. Revisit at the scale/compliance
   stage.
4. **Make every outward rule a hard lint.** Rejected: object-level authz, PII in
   prompts, and abuse-bounding are judgment calls no AST captures cleanly;
   forcing them into lints yields false positives or weak proxies. That is
   exactly why the ceiling is `manual` and owned by a reviewer with context.

## Consequences

- **Easier:** every non-trivial change gets a named frame ("which of the five
  faces does this touch?"); the floor is coverage-checked automatically; the
  ceiling has a designated checker instead of being nobody's job.
- **Harder:** someone must maintain `standards.example.json` and run the avatar
  lane; the grep/ast floor needs per-project path tuning (the shipped baseline
  is a starting point, not a finished config).
- **Now disallowed in spirit:** treating "it passes the lints" as "it is
  production-ready." Inward-clean no longer implies outward-safe, and the posture
  doc says so explicitly.
- **Staged to maturity:** controls scale with the project (prototype floor →
  first-users authn/authz + input validation → multi-user object-level authz +
  rate limits → scale threat-modeling). The failure mode is binary and both ends
  are real: ignoring the axis, or gold-plating a prototype with security
  theater. The §1 "naming ≠ adopting" rule applies unchanged.

## Verification

- `find-standard-gaps`' `standards.example.json` ships the baseline floor
  (resilience / security / observability / privacy / cost), grouped by
  dimension, with `ast`/`grep` detectors plus the `manual` ceiling entries; the
  scanner coverage-checks the floor on every run.
- `senior-engineer-posture.md` §4 and the `.augment/rules/imported/` mirror carry
  the framing; drift between them is caught by `find-augment-mirror-drift` /
  `find-rule-surface-drift`.
- The manual ceiling is owned by the review-avatar lane (prototype intact in the
  host project at `research/role-agents/`, including a `security-risk-engineer`
  role). See ADR 0019 for the trust-boundary half of the security story.
- **This ADR is `proposed`** until the avatar lane has run at least one pilot
  that checks code against the `manual` standards and produces a reviewed
  finding — i.e. until the ceiling has a demonstrated, not just declared, owner.
