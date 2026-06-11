# Skill Ecosystem Self-Review — Landscape & North-Star Alignment

Bounded, read-only diagnostic. 2026-05-25.

- **Center / canonical:** engineering-skills-2. **This sandbox (es3):** a clone
  we can explore and mess up; consolidation target → becomes v3.
- **Success criterion:** `VISION.md` (es2) — does the ecosystem embody, in its
  *own* structure, the end-state it pushes host projects toward (DRY, SOLID,
  real ideas explicit, the right ones promoted to standards, ideal shape,
  instant legibility)?
- **Trigger:** the quality/health skills have never been pointed at the
  ecosystem itself; the planning skills visibly overlap without a consistent
  standard; four parallel skill repos (engineering-skills 55 / -2 67 / -3 67 /
  pnci 64) drift with no declared canonical.

## 1. The ecosystem's actual shape (measured)

67 skills. Jobs and tiers:

```
JOB : suspect 28 | meta 11 | explain 9 | plan 6 | guard 2 | decide 2
      refactor 2 | teach 2 | map 2 | diagnose 1 | construct 1 | triage 1
TIER: maintenance 43 | cross-cutting 19 | system 4 | feature 1
```

**Read:** the ecosystem is overwhelmingly *detect-and-fix*. `suspect` is 42% of
all skills; `maintenance` tier is 64%. The **construct / understand / design /
compose** side — exactly the north-star's "arrive at the real ideas + the ideal
shape" — is nearly empty: 1 `construct`, 4 `system`, 1 `feature`, and the
shape-authoring skills (`audit-project-shape`, `map-project`,
`propose-architecture`) are still **intakes, not built**. The least-built corner
is the one the vision most needs.

## 2. Overlap clusters — the DRY problem, in our own house

| Cluster | Skills | Question |
|---|---|---|
| Duplication detectors ×4 | find-duplication, find-semantic-duplication, find-frontend-duplication, find-workflow-duplication | One parametrized family, or genuinely four skills? |
| Drift / staleness ~13 | find-*-drift (async-lifecycle, comment, contract, doc-route, folder-topology, frontend-contract, rule-surface, test-obligation), find-concept-divergence, find-stale-artifacts, find-workflow-state-gaps, check-ecosystem-consistency, find-skill-artifact-drift | A "drift detector" family on a shared scaffold? (cf. `ast-pipeline-detector-base` intake) |
| Planning / design / decision ~12 | plan(6: plan-feature, plan-skill, plan-spec, scope-feature, impact-feature, architecture-fit) + decide, design-it-twice + propose-boundary, propose-folder-reorganization | `which-skill` cannot route cleanly among these (see §4). |
| Idea / meta ~11 | track-, brainstorm-, extract-, mature-, find-orphaned-ideas + query-patterns + which-skill, which-shape + adapt-project, project-interview, orient, engineer-init | Bootstrapping + ideas + routing entangled under one `meta` job. |

## 3. Standards-consistency — one finding survived; one was my own false positive

- **RETRACTED (was: "the `job:` taxonomy is inconsistent").** I flagged
  `propose-boundary`, `extract-enum`, `unify-shadows`, etc. as mislabeled
  `job=explain`. They are **correct**: `skill-catalog.md` defines EXPLAIN as the
  *read-only proposal/brief* job — "EXPLAIN proposes the explicit form; REFACTOR
  executes it." Extract/propose skills emit a brief, so EXPLAIN is right. I
  nearly recommended relabeling correctly-labeled skills — and "fix-now" was
  authorized to *just do it*. **The near-miss is the real finding:** a skill
  operating on the skill system needs a *verify-intent-before-acting* control —
  the EXPLAIN semantic isn't self-evident from frontmatter alone, so a
  SUSPECT-style read misfires. (Skill-space analog of acting on a lint hit
  without reading why the code is that way.) Logged as **L4**.
- **`not_for` is advisory, not load-bearing.** `plan-feature` declares
  `not_for: new` yet still nearly wins "plan a *new* feature" (§4). Boundary
  metadata doesn't decisively penalize.

## 4. Routing evidence (`which-skill`, run as a dogfood)

- *"plan a new ... feature"* → `/scope-feature` (18) ≈ **ties** `/plan-feature`
  (16), and plan-feature takes its own `not_for: new` penalty yet nearly wins.
- *"decide whether to split X"* → `/refactor-subsystem`; **`/decide` never
  appears.**
- *"change how X works"* → limps to `/plan-feature` (7), no real home → the
  `make-change` gap (logged as an es2 intake 2026-05-25).

`find-skill-artifact-drift --gate` on the corpus is **clean** — so the problem
is *not* artifact integrity; it is overlap, routing, and taxonomy drift.

## 5. North-star coverage — "do we have skills for this?" (mostly yes)

| Vision facet | Existing machinery | Status |
|---|---|---|
| Extract real ideas + value | extract-existing-ideas, brainstorm-ideas, query-patterns, idea ledger | **HAVE** — but aimed at host prose, never run on the skill corpus itself |
| Which ideas are standards | harvest-learnings, find-standard-gaps, orient + which-shape (lifecycle × stakes, ADR 0020) | **HAVE the model** — not applied to the skills as subjects |
| Re-compose for DRY/SOLID | find-*-duplication, propose-boundary, unify-shadows, refactor-subsystem, triage-debt | **HAVE** |
| Ideal shape / folders | propose-folder-reorganization, find-folder-topology-drift, which-shape; audit-project-shape + map-project + propose-architecture are **intakes** | **PARTIAL** — least-built; the corner the vision most needs |
| Legibility / DX / docs | orient, engineer-init, project-interview, adapt-project, map-subsystem, ONBOARDING.md | **HAVE** — adequacy for "grasp instantly" untested |

**Punchline:** the machinery to do what the vision describes largely exists. It
has simply never been pointed at the ecosystem itself, and the one underbuilt
facet (ideal-shape/compose) is the vision's center of gravity.

## 6. Canonical drift across the four repos

No declared canonical and **no sync mechanism** — mirroring happens ad hoc as
one-off intakes (`mirror-find-broken-file-refs`, `find-doc-link-rot-skill`,
`find-folder-readme-drift-skill`, `find-rule-mirror-drift`,
`mirror-ast-lint-scaffold` …). Any fix in one copy re-drifts. That is *why* this
feels like a rabbit hole — until canonical + sync are settled.

- **Should be portable to es2 (currently pnci-only):** `find-spine-drift` +
  `propose-spine` (spine = a general multi-entry-workflow pattern, *not*
  pnci-specific — user-confirmed), `find-broken-file-refs`, `find-doc-link-rot`,
  `find-folder-readme-drift`; `find-augment-mirror-drift` → generalize to
  rule-mirror drift (es2 already has `find-rule-surface-drift`).
- **Should also reach pnci (currently es2-only):** `find-standard-gaps`,
  `find-skill-artifact-drift`, `check-ecosystem-consistency` (host self-audit),
  possibly `harvest-learnings`.
- **Pending decision:** es3 → v3 canonical; es2 = center; replace ad-hoc
  mirroring with one sync discipline.

## 7. Dispositions

**fix-now — both dissolved under the outcome-unit test (a good result, not a loss):**
- **F1 — RETRACTED.** Not a mislabel; EXPLAIN is deliberately the propose/brief
  job (§3). Nothing to relabel. The real item is a *control* → **L4**.
- **F2 — RESOLVED: keep separate.** The 4 duplication detectors aren't
  re-implementations — find-duplication (lexical/structural, jscpd+AST),
  find-semantic-duplication (*same problem, different code* — jscpd cannot reach
  these), find-frontend-duplication (UX shells / Tailwind / cotton primitives),
  find-workflow-duplication (product-step authority across layers). Distinct
  *outcomes* → keep separate, exactly like the SUSPECT family. The shared
  **triage-report + sub-agent fan-out scaffold** is the real consolidation
  candidate → **L1**.

**log (intake / backlog):**
- **L1** Drift/duplication detector-family consolidation on a shared *scaffold*
  (report + fan-out), cores stay distinct (cf. `ast-pipeline-detector-base`).
- **L2** Cross-repo skill **sync discipline** — replace the ad-hoc `mirror-*`
  intakes with one mechanism.
- **L3** Planning-cluster boundary redesign — `make-change` is one input;
  `which-shape` routing is the acceptance test.
- **L4** A *verify-intent-before-acting* control for skills that operate on the
  skill system (the dogfooding-controls path). Exhibit A: the F1 near-miss — a
  SUSPECT-style read of frontmatter flagged correct labels as wrong, and
  "fix-now" would have executed it. The skill-space analog of reading *why* code
  is shaped a certain way before "fixing" it.

**monitor:**
- **M1** Tier skew (maintenance-heavy) — re-evaluate as construct/greenfield
  skills land.

## 8. Recommended next step — point the ecosystem's skills inward (in es3)

Treat "does the skill even work on the skill corpus?" as itself a finding:

1. **Extract the real ideas + value** — cluster the 67 skills by the value each
   delivers (this doc starts it) → a canonical idea list, duplicates collapsed.
2. **Run `propose-folder-reorganization` / `which-shape` on `.claude/skills/`** →
   an ideal-shape proposal (do the 67 flat dirs become grouped by idea/job?).
3. **Run `find-duplication` / `find-semantic-duplication` on `skills/*/scripts/`**
   → mechanical DRY evidence for the families in §2.
4. **Apply `harvest-learnings` + lifecycle × stakes** → which ideas become
   always-on standards vs. stakes-gated activations.

## 9. Open questions for discussion

- Is the consolidation unit the **skill** (merge 4 dup-detectors) or the
  **idea** (one "duplication" idea, many activations)? — ties directly to "what
  are the real ideas."
- Standards: which extracted ideas become always-applied per job/situation, and
  is that enforced by `which-shape` / `harvest-learnings`, or by a new standards
  surface?
- Ideal shape: do the 67 flat skill dirs become grouped by job/idea-cluster?
  (folder-organization / ADR 0006: ≥3 siblings earn a package.)
