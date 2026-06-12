# ES Legacy Artifact Inventory

## .claude/tasks/ (direct files)

| path | what it is | kind | second-look? |
|---|---|---|---|
| `.claude/tasks/_adr_backfill_map.json` | skill↔ADR bidirectional & oneway claim maps; confirms judge/enforce vs mention | data | Y |
| `.claude/tasks/_adr_skillside_claims.json` | skill claims about ADR references; validates scope-feature, track-idea, query-patterns bindings | data | Y |
| `.claude/tasks/_fanout_brief.md` | "generate ES2 skill intent + provenance contracts (schema v2)"; parallel-agent contract authoring protocol | method | Y |
| `.claude/tasks/_fanout_partition.yaml` | "shared" + "es2_only" skill partition for contract fan-out; validates es2 coverage | data | Y |
| `.claude/tasks/adr0020-agentB-report.md` | ADR 0020 completion: /orient skill build report; covers SKILL.md, inference script, heuristics KB | design | Y |
| `.claude/tasks/class-a-remainder-notes.md` | host-path de-baking for propose-folder-reorganization & (implied) collect scripts; framework-convention → suffix logic | design | Y |
| `.claude/tasks/classbc-recon.md` | "read-only recon for removing hardcoded host paths"; scope.py & workflows.py API, detect.py hardcoded defaults | design | Y |
| `.claude/tasks/derive_skill_facts.py` | "Derive deterministic git + on-disk reports facts for every ES2 skill"; true-birth via parent-absence, runs from root | tool | Y |
| `.claude/tasks/es2_skill_facts.yaml` | "deterministic git + on-disk reports facts"; 68-skill count, birth cohorts, reports_dir, provenance | data | Y |
| `.claude/tasks/scans-frontmatter-sweep.md` | "Added explicit scans: frontmatter to 12 SUSPECT skills"; ADR 0032 evidence-based language coverage audit | run-history | Y |

## .claude/tasks/ecosystem-review/ (5 files)

| path | what it is | kind | second-look? |
|---|---|---|---|
| `ecosystem-review/01-landscape-and-north-star.md` | "Skill Ecosystem Self-Review — Landscape & North-Star"; measures 67 skills by job/tier; detect:guard ratio imbalance | design | Y |
| `ecosystem-review/02-inward-combined-pass.md` | "Does the ecosystem embody its own vision?"; three pillars (ideas, code, behavior); 68→~10 ideas, VISION.md self-test | design | Y |
| `ecosystem-review/02a-mechanical-duplication.md` | "8 clusters, ~2,700 LOC near-verbatim clone"; drift-detector scaffold cloned 4–6×, bypassed _common | design | Y |
| `ecosystem-review/02b-behavioral-conformance.md` | "Only 1 of 68 provable as-is (bucket A); 26 B, 40 C"; grading by side-effect, firing oracle availability | design | Y |
| `ecosystem-review/02c-ideal-shape-and-ideas.md` | "68 skills → ~10 ideas; flat → ~7–8 packages"; structural idea-family clustering analysis | design | Y |

## .claude/tasks/sweep-prototype/ (3 files)

| path | what it is | kind | second-look? |
|---|---|---|---|
| `sweep-prototype/atlas-ai-first-lessons.md` | "Lessons from Atlas for an AI-first toolkit"; 667k LOC TS study; diff-scoped guards cannot see integral-scoped rot; validates SUSPECT family | run-history | Y |
| `sweep-prototype/atlas-precision.md` | (structural file referenced by atlas-ai-first-lessons; metadata capture) | design | N |
| `sweep-prototype/sweep.py` | (implementation harness for sweep; excluded from scope) | tool | N |

## ai-docs/plans/ (4 files)

| path | what it is | kind | second-look? |
|---|---|---|---|
| `ai-docs/plans/consistency-session-execution.md` | Plan status: scoped; "every commitment lands, gets watched, or gets parked"; 22 ledger intakes, enforcement via find-orphaned-ideas | plan | Y |
| `ai-docs/plans/shareable-core-reorganization.md` | Plan status: scoped; embodiment tracker for ADR 0034 (layer migration); six workstreams, de-baking recon integration | plan | Y |
| `ai-docs/plans/skill-runtime-adherence-harness.md` | Plan status: draft; "Research aspiration"; three orthogonal skill-health axes; deferred execution | plan | Y |
| `ai-docs/plans/status-projection-and-presentation.md` | Plan status: promoted; spec successor; problem: project state scattered across reports/plans/ledger/engineering-state | plan | Y |

## ai-docs/specs/ (1 file)

| path | what it is | kind | second-look? |
|---|---|---|---|
| `ai-docs/specs/status-projection-and-presentation.md` | Spec status: draft; promoted from plan; code_roots: scripts/, tests/, which-shape/, extract-enum/, unify-shadows/ | plan | Y |

## reports/ (directory catalog only)

| subdir | file count | note |
|---|---|---|
| `reports/_meta/` | 4 | metadata housekeeping |
| `reports/adversarial-review/` | 1 | consistency-execution findings |
| `reports/architecture/` | 1 | |
| `reports/avatars/` | 2 | |
| `reports/check-ecosystem-consistency/` | 3 | |
| `reports/converge/` | 2 | |
| `reports/cotton-inventory/` | 1 | |
| `reports/find-comment-drift/` | 2 | |
| `reports/find-complexity-hotspots/` | 3 | |
| `reports/find-concept-divergence/` | 2 | |
| `reports/find-folder-topology-drift/` | 1 | |
| `reports/find-incomplete-sweep/` | 2 | |
| `reports/find-rule-surface-drift/` | 1 | |
| `reports/find-stale-artifacts/` | 2 | |
| `reports/harvest/` | 1 | |
| `reports/impact-feature/` | 2 | |
| `reports/meta-audit-kit-gaps/` | 1 | |
| `reports/omnibus/` | 2 | |
| `reports/plan-skill/` | 2 | |
| `reports/product-topology/` | 0 | |
| `reports/scope-feature/` | 1 | |
| `reports/skill-frame-review/` | 4 | |
| `reports/summary-pyramid/` | 1 | |
| `reports/which-cleanup/` | 2 | |

---

## Key Reusable Assets (second-look: Y items)

### High-Priority Methods & Protocols

1. **`_fanout_brief.md` + `_fanout_partition.yaml`** — Fan-out agent protocol for contract authoring; enables parallel skill-documentation work; proven pattern for multi-agent skill-facts derivation.

2. **`derive_skill_facts.py`** — Deterministic git-birth derivation (parent-absence validation, avoids merge artifacts); essential for skill-provenance tracking; transferable to any multi-skill ecosystem.

3. **`scans-frontmatter-sweep.md`** — Language-coverage audit method; ADR 0032 operationalization; provides templates for cross-checking detector implementation against declared coverage.

### Critical Design & Analysis Documents

4. **Ecosystem-review trio (`01-*`, `02-*`, `02a-*`, `02b-*`, `02c-*`)** — Complete self-diagnostic framework:
   - Idea-family clustering methodology (02c)
   - Mechanical-duplication detection & quantification (02a)
   - Behavioral grading by side-effect (02b: A/B/C bucket classification)
   - Structural imbalance finding: detect 27 : guard 1 (convergent evidence from three independent lenses)
   - Exportable as: skill-catalog reorganization roadmap, refactoring priority-setting, future ecosystem health audits.

5. **`atlas-ai-first-lessons.md`** — External validation of toolkit thesis; evidence that diff-scoped guards structurally cannot see integral-scoped rot; grounds SUSPECT family necessity in independent large-codebase study (667k LOC Atlas).

### Active Plans & Specifications

6. **`consistency-session-execution.md`** — Coordination plan pattern: committing ephemeral session outcomes to durable tracking via enumeration + enforcement machinery (find-orphaned-ideas --stale-plans).

7. **`shareable-core-reorganization.md`** — Embodiment tracker for ADR 0034 (layer migration); integrates class-a/b/c de-baking; roadmap for multi-workstream ecosystem refactoring.

8. **`status-projection-and-presentation.md` (plan + spec)** — Status-schema design; addresses routing bootstrap failure; spec includes code_roots for coverage tracking.

---

## ES2 Cross-Reference (indicates sibling-repo comparison happened)

- `_fanout_brief.md`: explicitly names "engineering-skills-2" as canonical; all ES2 facts in `.claude/tasks/es2_skill_facts.yaml`
- `_fanout_partition.yaml`: partitions "shared" (host-a contracted) vs "es2_only" skills
- `derive_skill_facts.py`: runs from ES2 root, derives 68-skill ES2 facts
- `es2_skill_facts.yaml`: output of above; deterministic capture of ES2 birth/provenance for contract fan-out
- Ecosystem-review: measures ES2 corpus explicitly; invokes `/find-duplication` self-audit (jscpd missing → cannot fully run on self)
