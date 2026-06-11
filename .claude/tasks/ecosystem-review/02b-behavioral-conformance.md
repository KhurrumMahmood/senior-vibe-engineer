# 02b — Behavioral Conformance: Pointing skill-comply at the ES3 Ecosystem

_Assessment date: 2026-05-25. Harness baseline: host-a/experiments/skill-comply/ Stages 1-2 (validate.py: OVERALL PASS, 5 fixtures). ES3 corpus: 67 skills with SKILL.md + _common shared library._

---

## Summary table

| Bucket | Count | Scoring it needs |
|---|---|---|
| **A — skill-comply-able ~as-is** | **1** | seed + install + score skeleton (C3/C4/C8) as-is; per-skill fixture pair + historical-fire replay |
| **B — side-effect-gradeable, different oracle** | **26** | new per-bucket scorers: characterization-test pass/fail for refactors; structural completeness + coverage oracle for proposers/docs/plans |
| **C — not behaviorally gradeable this way** | **40** | precision/recall against labeled ground truth for scanners; no path for pure routing/meta skills |

---

## 1. Model of skill-comply

skill-comply is a **conformance-by-side-effect** harness: it grades a skill run exclusively by (a) the artifacts the run leaves on disk and (b) the result of re-executing the skill's own verifiers against those artifacts — never by what the run claims. The anti-theater core is that a proposal can say "verification passed" and still fail, so every consequential check is a re-run, not a read.

The three load-bearing checks are C3, C4, and C8. **C3** re-runs the skill's own differential verifier (`verify_rule.py`), proving the fixture pair is internally self-consistent: the bad fixture fires and the good fixture is clean. This catches a rule too permissive to see its own anti-pattern or a fixture that is empty. **C4** is the historical-fire replay: for each file the anchor commit fixed, the rule must fire on `git show <anchor>^:<file>` (pre-fix source) and produce zero hits on HEAD. This is the anti-theater core — a rule whose matcher has drifted from the actual anti-pattern passes C3 (it is self-consistent with the fixtures it wrote) but fails C4 (it does not catch the real bug). The Stage-2 defective fixture proved this: all seven prior checks passed; only C4 exposed it. **C8** is the precision mirror: run the rule across the whole enforcement scope and require every hit to land in the known `antipattern_files` set. A rule that fires on innocent code will be `# noqa`'d into silence, after which it protects nothing, so over-firing is consequential. The Stage-1b Sonnet run passed all seven original checks and failed C8: its `request.<any-attr>.get(...)` matcher fired on `cart.py`'s `request.session.get(...)`, a server-trusted path, not user input.

The harness flags four gaps about itself. First, the **`antipattern_files` oracle problem**: C8 silently skips — and vacuously passes — when no `antipattern_files` are supplied. In the fixture world the seed manifest supplies that ground truth; in a real run "which files genuinely contain the pattern" is partly what the rule is *for*. Worse, a skip is a silent pass, not a surfaced state. Second, **"C8 skipped = silent pass"** makes any orchestration that forgets to supply the allowlist look green. Third, the **missing recall / false-negative axis**: C8 is a precision check (no stray firing); it cannot see a false negative on a variant the rule should match but doesn't (e.g., `self.request.POST.get(...)` in class-based views). Catching that requires a recall fixture — a known anti-pattern instance the rule must fire on and fails to — which is a different mechanism not yet built. Fourth, the **ruff-coverable Phase-1 branch is unmodeled**: when `prevent-regression` decides the pattern maps to an existing ruff rule, the artifact is a one-line `pyproject.toml` change; there is no rule script, no fixture pair, and no historical-fire replay, so the side-effect scorer has no surface to grade. Fifth, cross-skill generality is unproven: everything so far is one skill and one anti-pattern family.

---

## 2. Bucket-by-bucket classification

### Bucket A — skill-comply-able ~as-is (count: 1)

These skills emit a **runnable guard** (lint rule script + fixture pair + verify_rule, or an equivalent regression test) that must fire on a real historical bug and stay quiet on clean code. The seed/install/score skeleton targets this exact artifact shape. C3 checks internal fixture consistency via the skill's own verifier; C4 replays pre-anchor source through the rule; C8 runs the rule across the full enforcement scope against a known-clean decoy.

| Skill | Job | Why A |
|---|---|---|
| **prevent-regression** | guard | Emits a diff-scoped lint rule script + `tests/lint/<rule>_{bad,good}.<ext>` fixture pair + `verify_rule.py` verification + wiring (pre-commit hook, CI step, `run.py` RuleSpec, CLAUDE.md bullet). Also has a test-only guard branch (regression tests pinning route/import/auth contracts) that maps to the same C3/C4/C8 structure with a different execution path. The sole current exemplar in the harness. |

Note on `audit-decisions` (job: guard): despite the job label, it emits a ranked drift *report* (`drift.md`), not a runnable guard. It scans ADR registry state and surfaces advisory findings for human resolution. Scoring it requires precision/recall against labeled ground truth — bucket C logic — not C3/C4/C8.

---

### Bucket B — side-effect-gradeable, different oracle (count: 26)

These skills emit verifiable artifacts but not a "fires on a bug" guard. Each sub-group needs a dedicated scorer distinct from C3/C4/C8.

#### Refactor skills (2)

| Skill | Job | Artifact emitted | How to score |
|---|---|---|---|
| **fix-workflow** | refactor | Behavior-preserving commit(s) + regression test written first, then a separate bug-fix commit if latent issues surface. Runs the verification test matrix. | Oracle: characterization tests pass before and after; `git diff --stat` is bounded to the cluster; no new test failures introduced. A "before/after" behavioral equivalence check is the C4 analogue. |
| **refactor-subsystem** | refactor | Characterization tests (pinning imports, URL names, view callables from old paths), then the multi-commit split execution, then a Crystallize phase that updates docs. | Oracle: all characterization tests green after each phase; old import shims importable; no behavior regression. Needs a phase-gate scorer, not a single-shot check. |

#### Explain proposers (9)

These skills emit structured `proposal.md` documents with migration tables, caller impact summaries, and stop conditions. They are read-only (no code edits); the proposal is the artifact.

| Skill | Job | Artifact | How to score |
|---|---|---|---|
| **extract-enum** | explain | `reports/extract-enum/<target>/proposal.md` — enum class, caller migration table, data-migration risks, stop condition. | Oracle: proposal.md has required sections; every call site in `grep` output appears in the migration table; enum members cover all stringly-typed values found in the codebase. |
| **extract-state-type** | explain | `reports/extract-state-type/<target>/proposal.md` — current-shape table, proposed `@dataclass`/`TypedDict`, caller-by-caller migration plan, characterization-test matrix, stop condition. | Same completeness oracle; migration table coverage against grep output. |
| **introduce-fk** | explain | `reports/introduce-fk/<target>/proposal.md` — FK field shape, backfill migration sketch, caller migration table, tie-break strategy, risks. | Oracle: FK field shape is syntactically valid; backfill migration covers identified tuple-inferred identity sites. |
| **propose-boundary** | explain | `reports/propose-boundary/<target-slug>/proposal.md` — candidate seams, proposed public API, backward-compat shim shape, caller-impact summary, characterization-test matrix. | Oracle: every public symbol in the target file appears in the proposed API or the exclusion list; caller-impact summary covers all grep-identified callers. |
| **propose-folder-reorganization** | explain | `reports/propose-folder-reorganization/<...>/proposal.md` — reorganization plan respecting ADR 0006 packaging thresholds. | Oracle: proposal honors the "≥3 siblings → package" threshold; every file in scope appears in the plan. |
| **unify-shadows** | explain | `reports/unify-shadows/<finding-id>/proposal.md` — migration plan, caller impact, test matrix, stop condition for a `keep_separate_document_why | share_utilities | complete_migration | merge_at_workflow` finding. | Oracle: migration plan references the correct shape from `/find-semantic-duplication` output; test matrix covers reported callers. |
| **extract-cotton-primitive** | explain | Annotated template refactor brief — shared `<c-name />` Cotton component proposal. | Oracle: proposed component covers all duplicated shell variants identified in the source scan. |
| **extract-workflow-registry** | explain | Workflow-registry extraction proposal (canonicalize sidebar/dashboard step definitions). | Oracle: registry proposal covers all step definitions found in grep scan. |
| **explain-code** | explain | `reports/explanations/<target>.md` — annotated behavior doc per public symbol, pre/postconditions, invariants, callers, unexplained regions. | Oracle: every public symbol in the target file has an entry; callers listed match grep output; unexplained regions are either documented or flagged. |

#### Map skills (2)

| Skill | Job | Artifact | How to score |
|---|---|---|---|
| **map-subsystem** | map | `.claude/docs/subsystems/<name>.md` — file list, public surface, responsibility table, dependency graph, convention-compliance score. | Oracle: every file in the subsystem directory appears in the file list; public surface matches `grep -r 'def ' <dir>` output at a gross level. |
| **map-product-workflow** | map | Workflow inventory doc covering entry points, state transitions, and task/service mapping. | Oracle: entry points match `urls.py` grep; Celery task names match registered tasks. |

#### Diagnose skill (1)

| Skill | Job | Artifact | How to score |
|---|---|---|---|
| **diagnose** | diagnose | `diagnosis_report.md` + `reproduction_loop` (executable test/command) + `regression_test`. | Oracle: the reproduction loop is executable and fails before the fix (analogous to C4); the regression test is green after fix; root-cause hypothesis is falsifiable and matches the observed failure. The reproduction loop is the closest B-bucket analogue to C4. |

#### Construct skill (1)

| Skill | Job | Artifact | How to score |
|---|---|---|---|
| **harvest-learnings** | construct | Portable standards — each with attributed exemplar, host back-link, portability verdict (ports/stays-home via translation test), and lifecycle×stakes activation tag. | Oracle: translation test produces a syntactically valid host-adapted rule; portability verdict matches whether the standard's trigger condition applies in the target host. |

#### Decide skills (2)

| Skill | Job | Artifact | How to score |
|---|---|---|---|
| **decide** | decide | ADR at `ai-docs/decisions/<id>-<slug>.md` — problem, decision, status, applies_to, supersedes, alternatives, consequences. | Oracle: all required YAML frontmatter fields present; `applies_to:` paths exist on disk; no broken supersession back-reference. |
| **design-it-twice** | decide | Two-option analysis with explicit trade-off table, constraint list, and a selected option with rationale. | Oracle: both options are named and non-trivially different; trade-off table has ≥2 criteria; selected option is the one with the stated rationale. |

#### Triage skill (1)

| Skill | Job | Artifact | How to score |
|---|---|---|---|
| **triage-debt** | triage | `reports/triage-debt/scan-<TS>/queue.md` — ranked debt entries from cached find-* evidence, spec drift, decision drift. | Oracle: every queue entry has a linked evidence file that exists on disk; top-5 entries have a recommended next skill; recurrence entries have >1 dated scan reference. |

#### Plan skills (6)

| Skill | Job | Artifact | How to score |
|---|---|---|---|
| **plan-feature** | plan | `ai-docs/specs/<feature-name>.md` spec at `proposed` status — call sites mapped, behaviors-to-preserve listed, decision stubs for material forks. | Oracle: every touched subsystem has a call-site section; decision stubs are linked to real `ai-docs/decisions/` entries or marked `stub`. |
| **scope-feature** | plan | `ai-docs/plans/<name>.md` at `scoped` status — §1 (Scope & Bounds) and §2 (Success Criteria) filled. | Oracle: §1 and §2 present and non-trivial; plan status field updated to `scoped`. |
| **impact-feature** | plan | `ai-docs/plans/<name>.md` at `impacted` status — §3-4 filled with cross-subsystem blast radius. | Oracle: §3-4 present; every subsystem in the blast radius has a scout-output section. |
| **architecture-fit** | plan | `ai-docs/plans/<name>.md` at `architected` status — §5-6 filled, ADR candidates surfaced. | Oracle: §5-6 present; ADR candidates reference real smell IDs or decision IDs. |
| **plan-skill** | plan | Hardened skill spec with adversarial requirements pushback, trigger design, evidence contracts, dogfood cases, review gates. | Oracle: trigger design, evidence contracts, and at least one dogfood case present; not_for field non-empty. |
| **plan-spec** | plan | `ai-docs/specs/<spec-id>.md` promoted from plan — plan status set to `promoted`, spec scaffolded. | Oracle: spec file exists; plan status = `promoted`; `scripts/plans.py promote` exits 0. |

#### Teach skills (2)

| Skill | Job | Artifact | How to score |
|---|---|---|---|
| **teach-pattern** | teach | `reports/teach-pattern/scan-<TS>/<topic>.md` — five sections: rule, why, exemplar, counter-example, enforcement. | Oracle: all five sections present; exemplar references a real path that exists in the codebase; enforcement section either names a lint rule or explicitly says "none yet". |
| **gut-check** | teach | Post-implementation cross-cut check output covering test coverage, error-path handling, security, performance, and debt. | Oracle: each of the five check categories has a finding (pass/note/concern) and a recommendation. |

---

### Bucket C — not behaviorally gradeable this way (count: 40)

These skills emit advisory ranked candidate lists (suspect scanners) or provide pure routing/meta outputs. Scoring requires precision/recall against labeled ground truth, not a "did a guard fire" check.

#### Suspect scanners (28)

All 27 `find-*` skills plus `check-ecosystem-consistency` emit a ranked candidate list of code smells, drift symptoms, or deletion candidates. The right scoring instrument is: given a hand-labeled ground truth (known instances of the smell), what fraction did the scanner surface (recall) and what fraction of its findings are real (precision)? The harness has no mechanism for this.

| Skills | Notes |
|---|---|
| find-async-lifecycle-drift, find-comment-drift, find-complexity-hotspots, find-concept-divergence, find-contract-drift, find-dead-route-surface, find-doc-route-drift, find-dormant, find-duplication, find-folder-topology-drift, find-frontend-contract-drift, find-frontend-duplication, find-implicit-state, find-layer-violation, find-omnibus, find-orphaned-ideas, find-query-mutation, find-route-sprawl, find-rule-surface-drift, find-semantic-duplication, find-skill-artifact-drift, find-stale-artifacts, find-standard-gaps, find-test-obligation-drift, find-transaction-overreach, find-workflow-duplication, find-workflow-state-gaps | Each emits a `report.md` / `triage.md` with ranked candidate clusters. No runnable guard produced. |
| check-ecosystem-consistency | Suspect-job skill that produces a diff-aware ecosystem consistency snapshot, not a guard. Same precision/recall scoring problem. |

Note on `find-standard-gaps`: its `scripts/scan_coverage.py` is deterministic and the SKILL.md observes "a clean standard is a result... becomes a regression guard if re-run." This is the closest bucket-C skill to a bucket-A candidate. However, its primary artifact is a `coverage.md` report of gaps (candidate list), not a lint rule that fires on commits. Its re-run character is "audit again" not "block commit." If `scan_coverage.py` were wired as a pre-commit hook and given a ground-truth `standards.json`, it could be promoted to B or A; it is not there now.

#### Advisory drift scanner with guard-job label (1)

| Skill | Notes |
|---|---|
| **audit-decisions** (job: guard) | Despite the `guard` job label, this skill emits `reports/audit-decisions/scan-<TS>/drift.md` — a ranked list of drift symptoms (broken supersession chains, stale `proposed` ADRs, orphaned `# decision:` references, missing `applies_to:` paths). It does not produce a runnable lint rule or regression test. Grading it requires labeled ground truth (known-bad ADR registry state) against which precision/recall can be measured. Placed in bucket C. |

#### Meta / routing skills (11)

These skills produce routing recommendations, project-state JSON, idea-ledger entries, or pattern-lookup results. They are not behaviorally gradeable by side-effect in any bucket sense — correctness is a semantic judgment, not a structural artifact check.

| Skill | Why C |
|---|---|
| **which-skill** | Emits a skill recommendation. Grading = human judgment whether the recommendation was correct. |
| **which-shape** | Emits a problem-solving loop recommendation. Same. |
| **orient** | Writes `.project-state.json` with lifecycle/stakes classification. Grading = human verification of classification accuracy; the JSON structure is checkable but the values are judgment calls. |
| **adapt-project** | Emits host-project adaptation of ES3 standards. Grading = human review of adaptation accuracy. |
| **brainstorm-ideas** | Emits idea entries to the ledger. No behavioral artifact to check. |
| **mature-existing-ideas** | Annotates and matures existing idea-ledger entries. Advisory output. |
| **extract-existing-ideas** | Reads codebase and writes idea-ledger entries. Structured write but correctness is judgment-based. |
| **engineer-init** | Emits project-onboarding scaffolding. Structure checkable; correctness is judgment-based. |
| **project-interview** | Emits project intake doc from Q&A. Advisory. |
| **query-patterns** | Emits pattern lookup results from the pattern library. Read-only retrieval. |
| **track-idea** | Appends ledger record; schema validation is checkable but content is judgment-based. |

---

## 3. What generalizing skill-comply concretely requires

### Reusable as-is (seed/install/score skeleton + discipline)

The following pieces of the harness are **not skill-specific** and transport to any bucket-A skill without modification:

- **The conformance-by-side-effect discipline** — grade by artifacts + re-run verifiers, never by self-report. This principle applies to any skill that emits an executable artifact.
- **The seed/install/score separation** — `seed_fixture.py` builds an isolated throwaway target repo; `install_proposal.py` applies the proposal deterministically; `score_conformance.py` reads the result. The three-script pattern keeps the scorer honest (it only ever reads on-disk state). Any bucket-A skill can adopt this pattern.
- **The validate.py per-proposal isolation** — fresh `mkdtemp` repo per proposal, hermetic git identity, no cross-contamination. This is generic orchestration.
- **The verdict-space fixture methodology** — one conformant fixture proving the happy path; one defective per consequential check (C3, C4, C8 each have a designated defect). Building a full verdict space is the method for hardening any scorer. Transferable.
- **C3 as "re-run the skill's own verifier"** — the principle that the skill's own differential validity gate (`verify_rule.py`) is more trustworthy than a reimplemented check is generalizable. For any bucket-A skill, identify the analogous "skill's own verifier" and re-run it rather than re-implementing the check.

### Needs per-skill or new machinery

The following requires work per skill or per bucket. Each is tied to the harness's flagged limitations where applicable.

#### 1. The firing-scope oracle (antipattern_files) — ties to "C8 skipped = silent pass"

**The limitation:** C8 presumes a curated `antipattern_files` set. Without it C8 silently passes. In the fixture world the seed manifest supplies ground truth; in a real run "which files genuinely contain the pattern" is precisely what is uncertain. Any bucket-A generalization must solve this per-skill: either derive `antipattern_files` from the anchor's `fixed_files` (union reviewer-confirmed follow-on sites), or require the orchestration layer to supply a curated benign-decoy corpus. Missing this makes C8 theater.

**Concrete requirement:** every bucket-A skill needs a seed-manifest contract that supplies `antipattern_files` and `fixed_files` before the scorer runs. The validator must treat a missing `antipattern_files` as a surfaced state ("C8 skipped — oracle not supplied"), not a silent pass.

#### 2. A recall fixture per bucket-A skill — ties to "missing recall/false-negative axis"

**The limitation:** C8 is a precision check. Stage-1b finding #2 (the Sonnet rule misses `self.request.POST.get(...)` in class-based views) is a false negative invisible to C3/C4/C8. Catching false negatives requires a recall fixture: a known anti-pattern instance the rule must fire on but does not. This is a separate mechanism not yet built.

**Concrete requirement:** for each bucket-A skill, identify 2-3 variant anti-pattern instances the rule should catch beyond the main fixture. Add a recall fixture file and a C9 check: the rule must fire on every recall fixture with `hits > 0`. This is per-skill work (what variants exist depends on the anti-pattern) but the scoring mechanism is the same shape as C4.

#### 3. An entirely different scorer for bucket B

Bucket B skills produce code, proposals, and docs — not guards that fire on bugs. The C3/C4/C8 rubric has no surface to apply. Each sub-group needs its own oracle:

- **Refactors (fix-workflow, refactor-subsystem):** the oracle is behavioral equivalence under characterization tests. A "B-refactor scorer" checks: (a) characterization tests are written before the refactor; (b) they pass on the post-refactor HEAD; (c) `git diff --stat` is bounded to the stated scope; (d) no new test failures. The repair analogue of C4 is "does the pre-refactor test fail on the pre-refactor code and pass after?" — but this requires running the project test suite, not a standalone script.
- **Explain proposers (extract-enum, introduce-fk, etc.):** the oracle is structural completeness. A "B-explain scorer" checks: (a) proposal.md has all required sections (analogous to C1/C7 for structure); (b) every call site found by a reference grep appears in the migration table (analogous to C4's "does it cover the real instance?"). This is per-skill because required sections differ.
- **Plans / specs:** the oracle is section presence and status-field progression. Simpler than the guard scorer; a schema-validation pass with status-machine check is sufficient.

#### 4. An entirely different measurement approach for bucket C

Bucket C scanners output ranked candidate lists. The appropriate instrument is precision/recall against labeled ground truth. That requires:

- A labeled dataset (ground truth for at least one project): hand-curated lists of known smell instances for each scanner.
- A precision scorer: `hits that are real smells / total hits`.
- A recall scorer: `real smells found / total real smells`.

Neither the seed/install/score skeleton nor the C3/C4/C8 rubric has any bearing here. Building this is a larger undertaking than extending skill-comply; it is a separate evaluation framework.

Pure routing/meta skills (which-skill, which-shape, orient, etc.) do not have a behavioral scoring path at all — correctness is semantic and requires human judgment. Conformance for these reduces to structural artifact checks (does `.project-state.json` have the required fields? is the recommended skill in the known-skill list?) that are cosmetic in the C1 sense, not consequential.

#### 5. The ruff-coverable branch (unmodeled, intentionally deferred)

For `prevent-regression`'s Phase-1 "Ruff-first" path, the artifact is a `pyproject.toml` one-line enablement, not a rule script. The grading instrument must assert a negative (no bespoke script exists) plus that the enabled ruff code id actually covers the pattern. This is a config-diff + ruff-rule-id coverage assertion, not the side-effect scorer. It is flagged as a separate future probe in STAGE2.md and deferred here as well.

---

## Next steps (pended, not blocking)

1. **Stage 3: real-run orchestration for bucket A at scale.** Stage 1b proved one uncoached model run scores end-to-end for `prevent-regression`. Driving multiple runs across varied patterns needs an orchestration layer that distinguishes "stalled awaiting clarification" from "ran and produced nothing." The anti-pattern_files oracle must be resolved before C8 is meaningful.

2. **Recall fixture for prevent-regression (highest-value near-term addition).** Add a C9 check exercising `self.request.POST.get(...)` and aliased receivers — the Stage-1b finding #2 that C3/C4/C8 cannot see.

3. **Bucket B pilot: fix-workflow with a characterization-test oracle.** The characterization-test pattern is already the skill's own discipline; a scorer that checks "tests written before, pass after, scope bounded" would be a natural second pilot.

4. **find-standard-gaps re-evaluation as a bucket A/B candidate.** `scan_coverage.py` is deterministic and already has the structure of a runnable scanner. If `standards.json` is treated as the seed manifest and the scan is run in pre-commit mode, it could be scored with a C4-analogue (did the gap fire on the known-bad standard site?) and a C8-analogue (did it stay quiet on compliant sites?).
