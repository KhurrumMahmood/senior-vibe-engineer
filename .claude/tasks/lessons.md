# Task lessons

Append-only diary. Add a dated entry when completed work changes how future
work should be approached. Each entry states the rule, why it exists, and how
to apply it. Do not use this file as a progress tracker or backlog.

## 2026-07-18 — Productization must begin at the public journey

- **Rule:** Before designing distribution infrastructure, run the simplest
  standard installer against the actual repository, install one unit into an
  empty host, and execute it outside the source checkout.
- **Why:** `skills@1.5.19` already discovered all 76 skills at `ad685e3` and
  installed the two routers. The real failure was only that the installed
  routers imported repository-level modules. We spent most of an 82k-line
  expansion protecting a custom installer that the ordinary product did not
  need.
- **Apply:** The first acceptance check for installation is a clean-host
  install-to-use journey. A custom installer or lifecycle wrapper requires a
  demonstrated stock-tool blocker and explicit scope approval.

## 2026-07-18 — Plans and proofs are not product progress

- **Rule:** Count progress only when a required user journey or skill family
  becomes newly usable at the current revision.
- **Why:** Phase gates, contracts, receipts, independent reviews, and hundreds
  of passing tests advanced while mandatory public journeys stayed at zero.
  The control plane was internally green but did not invoke a public installer
  or a TypeScript skill workflow.
- **Apply:** Show separate numerators for user journeys, completed skill
  families, and supporting activity. If two hours or two accepted product
  commits pass without moving a product numerator, stop and reassess scope.

## 2026-07-18 — Adversarial review must be able to reject the architecture

- **Rule:** A review finding should not automatically add another contract or
  proof layer; it must be allowed to conclude that the protected mechanism is
  unnecessary.
- **Why:** Reviews correctly found local bypasses, but each repair hardened the
  same wrongly prioritized platform. Local correctness improved while global
  alignment worsened.
- **Apply:** For every severe review finding, ask both “how do we repair this?”
  and “does this mechanism belong on the critical path?” Prefer deletion or
  deferral when no required journey depends on it.

## 2026-07-18 — Cross-language work is batched by invariant family

- **Rule:** Generalize a cohesive skill family in one isolated worktree rather
  than creating one language variant per skill or making all families share a
  single implementation lane.
- **Why:** Family members usually share detection facts, change semantics, and
  guard generation. Family-sized work permits reuse without forcing unrelated
  skills through a global abstraction.
- **Apply:** Inventory all skills first. Freeze one Python/TypeScript vertical
  slice. Then assign one fresh-context worker per independent family, cap
  concurrency, and keep shared adapters/registries under one serial owner.

## 2026-07-18 — High-assurance distribution is a separate product hypothesis

- **Rule:** Content-bound packages, transactional recovery, hostile mutation
  tests, cross-surface capability matrices, and execution attestations are an
  optional high-assurance runtime—not the default open-source installer.
- **Why:** Those mechanisms may be valuable for regulated, offline,
  enterprise, or untrusted-distribution environments, but their threat model
  and complexity are disproportionate for ordinary Git-hosted skills.
- **Apply:** Explore the archived prototype only after identifying a customer,
  threat model, and required journey that standard Agent Skills tooling cannot
  satisfy. Recover one bounded capability slice at a time; never merge the
  archive wholesale.

## 2026-07-18 — Optimize execution only after a useful path works

- **Rule:** Do not build a generic coordinator, context cache, or benchmark
  harness before representative installed workflows exist.
- **Why:** Efficiency work without a useful final-output path optimizes an
  invented workload and can become another substrate-first loop.
- **Apply:** First freeze real tasks and outcome checks. Then measure wall
  time, tokens, repeated context, and interventions. Batch independent
  read-only lenses; serialize mutations. Add shared orchestration only when
  measured fixed workflows demonstrate the need.
