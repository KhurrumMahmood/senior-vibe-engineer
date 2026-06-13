# Catalog stabilization — wave plan (2026-06-12)

Goal (user directive): every skill fixed to the activation standard
(`repair-skill/knowledge/skill-standard.md`) — the catalog is not
shareable while half is unstable. Triage basis: batch-1..5 + the
adversarial passes in this directory. ~37/66 NEEDS-REPAIR, ~23 MINOR.
Execution: Codex lanes, ≤5 parallel (CLAUDE.local.md cap), each skill
owned by exactly ONE lane which fixes ALL its findings. Lanes verify
findings against ground truth before fixing (TRUE/PARTLY/FALSE),
instantiate standard elements from exemplar shapes with the skill's
own nouns, self-check citations, run skill_meta.py lint + smokes; no
commits (orchestrator verifies and commits per lane).

## Wave 1 (dispatched)

| Lane | Skills / surfaces |
|---|---|
| W1-1 host-residue | _common/dispatch_scout_cheap.sh (host-adapter probe), find-dormant, find-async-lifecycle-drift, find-contract-drift, find-dead-route-surface, + one-line dispatch caveats in which-cleanup / propose-boundary |
| W1-2 scanner A | find-route-sprawl, find-rule-surface-drift, find-skill-artifact-drift, find-stale-artifacts, find-perimeter-gaps |
| W1-3 scanner B | find-skill-intent-drift, find-semantic-duplication, find-orphaned-ideas, find-incomplete-sweep (incl. placeholder-band --project-root code fix) |
| W1-4 batch-1 heavy | audit-decisions (phantom /decide forms), converge, check-ecosystem-consistency, adapt-project |
| (parallel) coverage | adversarial on batch-1 OKs + batch-4 OK/MINOR re-derivation |

## Wave 2 (queued — dispatch as W1 lanes free)

| Lane | Skills |
|---|---|
| W2-1 extract family | extract-cotton-primitive (exit-code lie), extract-existing-ideas (approval set never written back), extract-state-type (Form A unimplemented), extract-workflow-registry (triple contract drift) |
| W2-2 batch-4 NRs a | find-standard-gaps, find-transaction-overreach, find-workflow-duplication |
| W2-3 batch-4 NRs b | find-workflow-state-gaps, introduce-fk, map-subsystem |
| W2-4 batch-5 NRs | triage-debt (--top parse bug), unify-shadows (empty knowledge/ templates), project-interview (artifact-root contract break), query-patterns |

## Wave 3 (queued)

| Lane | Skills |
|---|---|
| W3-1 drift pair + scanners | find-folder-topology-drift, find-frontend-contract-drift (default-root contradictions), find-comment-drift, find-complexity-hotspots, find-concept-divergence, find-doc-route-drift (standard gates) |
| W3-2 MINOR batch 1 | brainstorm-ideas, decide (template refresh), engineer-init, explain-code, extract-enum |
| W3-3 MINOR batch 2 | find-duplication, find-frontend-duplication, find-implicit-state, find-layer-violation, find-omnibus, find-query-mutation (replay evidence + small fixes) |
| W3-4 MINOR batch 3 | plan-feature, plan-spec, propose-boundary, propose-folder-reorganization, teach-pattern, track-idea, which-cleanup, which-skill (+ any batch-4 re-derived MINORs) |

## Post-wave gates

1. Detector hardening via /prevent-regression: extend
   find-skill-artifact-drift from existence-checks to behavior-checks
   (defaults match argparse, advertised flags forwarded, emitted
   patterns listed, exit codes honored) — kills the doc/script-drift
   class at commit time.
2. Re-triage spot-check: one fresh frame review per wave's worst skill
   (different model than the fixer) before declaring the catalog stable.
3. skill-comply / oracle growth tracks separately (Bucket-B program).
4. Ledgered, not in waves: code-agent-runtime-port (restores cheap
   dispatch properly), fix-workflow residual sweeps (78 bare-knowledge/
   refs, 8 host-bound-command files, cluster: routing, dead-path appends).
